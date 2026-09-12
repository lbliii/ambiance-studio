#import "media_common.h"
#import "media_commands.h"
#import "verify_audio.h"
#import <ImageIO/ImageIO.h>
#include <math.h>

static void savePixel(CVPixelBufferRef pb, NSString *path) {
    CVPixelBufferLockBaseAddress(pb, kCVPixelBufferLock_ReadOnly);
    CGColorSpaceRef space = CGColorSpaceCreateWithName(kCGColorSpaceSRGB);
    CGContextRef c =
        CGBitmapContextCreate(CVPixelBufferGetBaseAddress(pb), CVPixelBufferGetWidth(pb),
                              CVPixelBufferGetHeight(pb), 8, CVPixelBufferGetBytesPerRow(pb), space,
                              kCGBitmapByteOrder32Little | kCGImageAlphaPremultipliedFirst);
    CGImageRef image = CGBitmapContextCreateImage(c);
    CGImageDestinationRef destination = CGImageDestinationCreateWithURL(
        (__bridge CFURLRef)[NSURL fileURLWithPath:path], CFSTR("public.png"), 1, NULL);
    if (!destination)
        fail(@"Cannot create PNG");
    CGImageDestinationAddImage(destination, image, NULL);
    if (!CGImageDestinationFinalize(destination))
        fail(@"PNG save failed");
    CFRelease(destination);
    CGImageRelease(image);
    CGContextRelease(c);
    CGColorSpaceRelease(space);
    CVPixelBufferUnlockBaseAddress(pb, kCVPixelBufferLock_ReadOnly);
}
static NSData *pixelBytes(CVPixelBufferRef pb) {
    CVPixelBufferLockBaseAddress(pb, kCVPixelBufferLock_ReadOnly);
    size_t width = CVPixelBufferGetWidth(pb), height = CVPixelBufferGetHeight(pb),
           stride = CVPixelBufferGetBytesPerRow(pb);
    NSMutableData *data = [NSMutableData dataWithLength:width * height * 4];
    for (size_t y = 0; y < height; y++)
        memcpy((unsigned char *)data.mutableBytes + y * width * 4,
               (unsigned char *)CVPixelBufferGetBaseAddress(pb) + y * stride, width * 4);
    CVPixelBufferUnlockBaseAddress(pb, kCVPixelBufferLock_ReadOnly);
    return data;
}
static NSDictionary *pixelDifference(NSData *a, NSData *b) {
    if (a.length != b.length || !a.length)
        return @{@"comparable" : @NO};
    const unsigned char *left = a.bytes, *right = b.bytes;
    double sum = 0;
    int maximum = 0;
    for (size_t i = 0; i < a.length; i++)
        if (i % 4 != 3) {
            int d = abs((int)left[i] - (int)right[i]);
            sum += d;
            maximum = MAX(maximum, d);
        }
    return @{
        @"comparable" : @YES,
        @"rgb_mean_absolute_difference" : @(sum / (a.length / 4 * 3)),
        @"rgb_max_difference" : @(maximum)
    };
}
void verify(NSString *path, int width, int height, int fps, int expectedFrames, int expectedAudio,
            NSString *reportPath, NSString *framesPath, int loopFrames,
            NSString *requestedContacts) {
    AVURLAsset *source = asset(path);
    NSArray *videos = [source tracksWithMediaType:AVMediaTypeVideo],
            *sounds = [source tracksWithMediaType:AVMediaTypeAudio];
    if (videos.count != 1)
        fail(@"Expected exactly one video track");
    AVAssetTrack *track = videos.firstObject;
    NSError *error = nil;
    AVAssetReader *reader = [[AVAssetReader alloc] initWithAsset:source error:&error];
    AVAssetReaderTrackOutput *output = [AVAssetReaderTrackOutput
        assetReaderTrackOutputWithTrack:track
                         outputSettings:@{
                             (NSString *)
                             kCVPixelBufferPixelFormatTypeKey : @(kCVPixelFormatType_32BGRA)
                         }];
    output.alwaysCopiesSampleData = NO;
    [reader addOutput:output];
    if (![reader startReading])
        fail(reader.error.description);
    int count = 0;
    double previous = -1, maxTimingError = 0, lastEnd = 0;
    BOOL ordered = YES;
    CMSampleBufferRef sample;
    NSMutableSet *contacts = [NSMutableSet setWithArray:@[
        @0, @1, @(expectedFrames - 1), @(MAX(0, expectedFrames - 2)), @(loopFrames / 4),
        @(loopFrames / 2), @(loopFrames * 3 / 4)
    ]];
    for (int join = loopFrames; join < expectedFrames; join += loopFrames) {
        [contacts addObject:@(join - 2)];
        [contacts addObject:@(join - 1)];
        [contacts addObject:@(join)];
        [contacts addObject:@(join + 1)];
    }
    if (requestedContacts.length)
        for (NSString *index in [requestedContacts componentsSeparatedByString:@","]) {
            NSScanner *scanner = [NSScanner scannerWithString:index];
            int frame = -1;
            if (![scanner scanInt:&frame] || !scanner.isAtEnd || frame < 0 ||
                frame >= expectedFrames)
                fail(@"Requested contact frame is out of range");
            [contacts addObject:@(frame)];
        }
    for (NSNumber *index in contacts.allObjects)
        if (index.intValue < 0 || index.intValue >= expectedFrames)
            [contacts removeObject:index];
    NSData *firstPixels = nil, *previousPixels = nil;
    NSMutableArray *joins = [NSMutableArray array];
    BOOL decodedDimensions = YES;
    while ((sample = [output copyNextSampleBuffer])) {
        @autoreleasepool {
            double stamp = CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(sample));
            if (stamp <= previous)
                ordered = NO;
            maxTimingError = fmax(maxTimingError, fabs(stamp - (double)count / fps));
            previous = stamp;
            // AVAssetReader may return invalid duration on decoded images. Ordered exact
            // CFR PTS establishes one-frame presentation duration independently.
            double sampleDuration = CMTimeGetSeconds(CMSampleBufferGetDuration(sample));
            lastEnd = stamp +
                      (isfinite(sampleDuration) && sampleDuration > 0 ? sampleDuration : 1.0 / fps);
            if (![framesPath isEqualToString:@"-"] && [contacts containsObject:@(count)])
                savePixel(
                    CMSampleBufferGetImageBuffer(sample),
                    [framesPath
                        stringByAppendingPathComponent:[NSString
                                                           stringWithFormat:@"decoded-%04d.png",
                                                                            count]]);
            CVPixelBufferRef pixels = CMSampleBufferGetImageBuffer(sample);
            if (!pixels || CVPixelBufferGetWidth(pixels) != width ||
                CVPixelBufferGetHeight(pixels) != height)
                decodedDimensions = NO;
            NSData *currentPixels = pixels ? pixelBytes(pixels) : nil;
            if (count == 0)
                firstPixels = currentPixels;
            else if (count % loopFrames == 0)
                [joins addObject:@{
                    @"frame" : @(count),
                    @"last_to_first" : pixelDifference(previousPixels, currentPixels),
                    @"first_frame_to_repeated_start" : pixelDifference(firstPixels, currentPixels)
                }];
            previousPixels = currentPixels;
            count++;
            CFRelease(sample);
        }
    }
    BOOL complete = reader.status == AVAssetReaderStatusCompleted;
    NSDictionary *audio = verifyAudio(source, sounds, expectedFrames, fps, framesPath);
    double expectedSeconds = (double)expectedFrames / fps;
    BOOL ok = complete && decodedDimensions && ordered && count == expectedFrames &&
              track.naturalSize.width == width && track.naturalSize.height == height &&
              fabs(track.nominalFrameRate - fps) < 1e-5 && maxTimingError < 1e-5 &&
              fabs(CMTimeGetSeconds(source.duration) - expectedSeconds) < 1e-5 &&
              fabs(CMTimeGetSeconds(track.timeRange.start)) < 1e-6 &&
              fabs(CMTimeGetSeconds(track.timeRange.duration) - expectedSeconds) < 1e-5 &&
              fabs(lastEnd - expectedSeconds) < 1e-5 && sounds.count == expectedAudio &&
              [audio[@"fully_decoded"] boolValue];
    if (sounds.count)
        ok = ok && [audio[@"contiguous_presented_samples"] boolValue] &&
             fabs([audio[@"presented_end_seconds"] doubleValue] - expectedSeconds) <=
                 1.0 / 48000 + 1e-8 &&
             [audio[@"monotonic_timestamps"] boolValue] &&
             [audio[@"sample_rate"] doubleValue] == 48000 && [audio[@"channels"] intValue] == 2 &&
             fabs([audio[@"track_start"] doubleValue]) < 1e-6 &&
             fabs([audio[@"track_duration"] doubleValue] - expectedSeconds) < 1.0 / 48000 &&
             llabs([audio[@"presented_samples"] longLongValue] -
                   llround(expectedSeconds * [audio[@"sample_rate"] doubleValue])) <= 1;
    json(
        @{
            @"ok" : @(ok),
            @"file" : path,
            @"duration_seconds" : @(CMTimeGetSeconds(source.duration)),
            @"width" : @(track.naturalSize.width),
            @"height" : @(track.naturalSize.height),
            @"fps" : @(track.nominalFrameRate),
            @"decoded_frames" : @(count),
            @"fully_decoded" : @(complete),
            @"monotonic_timestamps" : @(ordered),
            @"max_frame_pts_error_seconds" : @(maxTimingError),
            @"last_video_sample_end_seconds" : @(lastEnd),
            @"video_track_start_seconds" : @(CMTimeGetSeconds(track.timeRange.start)),
            @"video_track_duration_seconds" : @(CMTimeGetSeconds(track.timeRange.duration)),
            @"audio" : audio,
            @"decoded_dimensions_match" : @(decodedDimensions),
            @"contact_frames" : [contacts.allObjects sortedArrayUsingSelector:@selector(compare:)],
            @"loop_frames" : @(loopFrames),
            @"joins" : joins,
            @"file_last_to_first" : pixelDifference(previousPixels, firstPixels),
            @"join_metrics_are_not_artistic_approval" : @YES,
            @"visual_review_performed" : @NO,
            @"human_listening_review_performed" : @NO
        },
        reportPath);
    if (!ok)
        fail(@"Media validation failed; inspect report");
}
