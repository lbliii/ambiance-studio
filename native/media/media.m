// Shared macOS AVFoundation backend. See docs/RENDERING.md for validation scope.
// Promoted from The Midnight Collection; retains sync-frame preroll and PCM mux fixes.
#import <Foundation/Foundation.h>
#import <AVFoundation/AVFoundation.h>
#import <ImageIO/ImageIO.h>
#import <CoreVideo/CoreVideo.h>
#import <CommonCrypto/CommonDigest.h>
#include <unistd.h>
#include <math.h>

static void fail(NSString *message) {
    fprintf(stderr, "%s\n", message.UTF8String);
    exit(1);
}
static void fresh(NSString *path) {
    if ([[NSFileManager defaultManager] fileExistsAtPath:path])
        fail([@"Refusing to overwrite: " stringByAppendingString:path]);
}
static AVURLAsset *asset(NSString *path) {
    if (![[NSFileManager defaultManager] fileExistsAtPath:path])
        fail([@"Missing: " stringByAppendingString:path]);
    return [AVURLAsset URLAssetWithURL:[NSURL fileURLWithPath:path]
                               options:@{
                                   AVURLAssetPreferPreciseDurationAndTimingKey : @YES
                               }];
}
static void json(NSDictionary *value, NSString *path) {
    NSError *error = nil;
    NSData *data =
        [NSJSONSerialization dataWithJSONObject:value
                                        options:NSJSONWritingPrettyPrinted | NSJSONWritingSortedKeys
                                          error:&error];
    if (!data)
        fail(error.description);
    if (path && ![data writeToFile:path options:NSDataWritingAtomic error:&error])
        fail(error.description);
    puts([[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding].UTF8String);
}
static void finish(AVAssetWriter *writer) {
    dispatch_semaphore_t done = dispatch_semaphore_create(0);
    [writer finishWritingWithCompletionHandler:^{
      dispatch_semaphore_signal(done);
    }];
    dispatch_semaphore_wait(done, DISPATCH_TIME_FOREVER);
    if (writer.status != AVAssetWriterStatusCompleted)
        fail(writer.error.description ?: @"Writer failed");
}
static void ready(AVAssetWriterInput *input, AVAssetWriter *writer) {
    while (!input.readyForMoreMediaData) {
        if (writer.status == AVAssetWriterStatusFailed ||
            writer.status == AVAssetWriterStatusCancelled)
            fail(writer.error.description ?: @"Writer stopped");
        usleep(1000);
    }
}
static void encode(NSString *path, int width, int height, int fps, int frames, int bitrate,
                   int keyInterval) {
    fresh(path);
    if (width < 2 || height < 2 || width % 2 || height % 2 || fps < 1 || frames < 1)
        fail(@"Invalid encoding dimensions/timing");
    NSError *error = nil;
    AVAssetWriter *writer = [[AVAssetWriter alloc] initWithURL:[NSURL fileURLWithPath:path]
                                                      fileType:AVFileTypeMPEG4
                                                         error:&error];
    if (!writer)
        fail(error.description);
    NSDictionary *compression = @{
        AVVideoAverageBitRateKey : @(bitrate),
        AVVideoExpectedSourceFrameRateKey : @(fps),
        AVVideoMaxKeyFrameIntervalKey : @(keyInterval),
        AVVideoAllowFrameReorderingKey : @NO,
        AVVideoProfileLevelKey : AVVideoProfileLevelH264HighAutoLevel
    };
    NSDictionary *color = @{
        AVVideoColorPrimariesKey : AVVideoColorPrimaries_ITU_R_709_2,
        AVVideoTransferFunctionKey : AVVideoTransferFunction_ITU_R_709_2,
        AVVideoYCbCrMatrixKey : AVVideoYCbCrMatrix_ITU_R_709_2
    };
    AVAssetWriterInput *input =
        [AVAssetWriterInput assetWriterInputWithMediaType:AVMediaTypeVideo
                                           outputSettings:@{
                                               AVVideoCodecKey : AVVideoCodecTypeH264,
                                               AVVideoWidthKey : @(width),
                                               AVVideoHeightKey : @(height),
                                               AVVideoCompressionPropertiesKey : compression,
                                               AVVideoColorPropertiesKey : color
                                           }];
    input.expectsMediaDataInRealTime = NO;
    AVAssetWriterInputPixelBufferAdaptor *adaptor = [AVAssetWriterInputPixelBufferAdaptor
        assetWriterInputPixelBufferAdaptorWithAssetWriterInput:input
                                   sourcePixelBufferAttributes:@{
                                       (NSString *)kCVPixelBufferPixelFormatTypeKey :
                                           @(kCVPixelFormatType_32BGRA),
                                       (NSString *)kCVPixelBufferWidthKey : @(width),
                                       (NSString *)kCVPixelBufferHeightKey : @(height),
                                       (NSString *)kCVPixelBufferCGImageCompatibilityKey : @YES,
                                       (NSString *)
                                       kCVPixelBufferCGBitmapContextCompatibilityKey : @YES
                                   }];
    if (![writer canAddInput:input])
        fail(@"Cannot add video encoder");
    [writer addInput:input];
    if (![writer startWriting])
        fail(writer.error.description);
    [writer startSessionAtSourceTime:kCMTimeZero];
    size_t frameBytes = (size_t)width * height * 4;
    unsigned char *rgba = malloc(frameBytes);
    if (!rgba)
        fail(@"Raw frame allocation failed");
    for (int frame = 0; frame < frames; frame++) {
        @autoreleasepool {
            size_t received = 0;
            while (received < frameBytes) {
                size_t n = fread(rgba + received, 1, frameBytes - received, stdin);
                if (!n)
                    fail([NSString
                        stringWithFormat:@"Incomplete RGBA stream at frame %d: %zu/%zu bytes",
                                         frame, received, frameBytes]);
                received += n;
            }
            ready(input, writer);
            CVPixelBufferRef pb = NULL;
            if (CVPixelBufferPoolCreatePixelBuffer(NULL, adaptor.pixelBufferPool, &pb) !=
                kCVReturnSuccess)
                fail(@"Pixel buffer allocation failed");
            CVPixelBufferLockBaseAddress(pb, 0);
            unsigned char *base = CVPixelBufferGetBaseAddress(pb);
            size_t stride = CVPixelBufferGetBytesPerRow(pb);
            for (int y = 0; y < height; y++) {
                unsigned char *src = rgba + (size_t)y * width * 4, *dst = base + (size_t)y * stride;
                for (int x = 0; x < width; x++) {
                    dst[4 * x] = src[4 * x + 2];
                    dst[4 * x + 1] = src[4 * x + 1];
                    dst[4 * x + 2] = src[4 * x];
                    dst[4 * x + 3] = src[4 * x + 3];
                }
            }
            CVPixelBufferUnlockBaseAddress(pb, 0);
            BOOL ok = [adaptor appendPixelBuffer:pb withPresentationTime:CMTimeMake(frame, fps)];
            CVPixelBufferRelease(pb);
            if (!ok)
                fail(writer.error.description);
            if (frame % 120 == 0)
                fprintf(stderr, "Encoded frame %d/%d\n", frame, frames);
        }
    }
    free(rgba);
    [input markAsFinished];
    [writer endSessionAtSourceTime:CMTimeMake(frames, fps)];
    finish(writer);
    json(
        @{
            @"ok" : @YES,
            @"file" : path,
            @"frames" : @(frames),
            @"width" : @(width),
            @"height" : @(height),
            @"fps" : @(fps),
            @"seconds" : @((double)frames / fps),
            @"codec" : @"H.264 High",
            @"bitrate" : @(bitrate)
        },
        nil);
}
static void encodeAudio(NSString *sourcePath, NSString *outPath) {
    fresh(outPath);
    AVURLAsset *source = asset(sourcePath);
    AVAssetTrack *track = [source tracksWithMediaType:AVMediaTypeAudio].firstObject;
    if (!track)
        fail(@"Missing audio track");
    NSError *error = nil;
    AVAssetReader *reader = [[AVAssetReader alloc] initWithAsset:source error:&error];
    if (!reader)
        fail(error.description);
    AVAssetReaderTrackOutput *output =
        [AVAssetReaderTrackOutput assetReaderTrackOutputWithTrack:track
                                                   outputSettings:@{
                                                       AVFormatIDKey : @(kAudioFormatLinearPCM),
                                                       AVLinearPCMBitDepthKey : @16,
                                                       AVLinearPCMIsFloatKey : @NO,
                                                       AVLinearPCMIsBigEndianKey : @NO,
                                                       AVLinearPCMIsNonInterleaved : @NO
                                                   }];
    [reader addOutput:output];
    AVAssetWriter *writer = [[AVAssetWriter alloc] initWithURL:[NSURL fileURLWithPath:outPath]
                                                      fileType:AVFileTypeAppleM4A
                                                         error:&error];
    if (!writer)
        fail(error.description);
    AVAssetWriterInput *input =
        [AVAssetWriterInput assetWriterInputWithMediaType:AVMediaTypeAudio
                                           outputSettings:@{
                                               AVFormatIDKey : @(kAudioFormatMPEG4AAC),
                                               AVSampleRateKey : @48000,
                                               AVNumberOfChannelsKey : @2,
                                               AVEncoderBitRateKey : @256000
                                           }];
    [writer addInput:input];
    if (![writer startWriting] || ![reader startReading])
        fail(writer.error.description ?: reader.error.description);
    [writer startSessionAtSourceTime:kCMTimeZero];
    CMSampleBufferRef sample;
    while ((sample = [output copyNextSampleBuffer])) {
        @autoreleasepool {
            ready(input, writer);
            BOOL ok = [input appendSampleBuffer:sample];
            CFRelease(sample);
            if (!ok)
                fail(writer.error.description);
        }
    }
    if (reader.status != AVAssetReaderStatusCompleted)
        fail(reader.error.description ?: @"Incomplete audio source decode");
    // AVAssetWriter derives AAC priming/padding edits from consumed PCM timing.
    [input markAsFinished];
    finish(writer);
    json(
        @{
            @"ok" : @YES,
            @"source" : sourcePath,
            @"file" : outPath,
            @"codec" : @"AAC",
            @"sample_rate" : @48000,
            @"channels" : @2,
            @"bitrate" : @256000,
            @"source_seconds" : @(CMTimeGetSeconds(source.duration))
        },
        nil);
}
static void trimPicture(NSString *sourcePath, NSString *outPath, int skipFrames, int frames,
                        int fps) {
    fresh(outPath);
    AVURLAsset *source = asset(sourcePath);
    AVAssetTrack *track = [source tracksWithMediaType:AVMediaTypeVideo].firstObject;
    if (!track)
        fail(@"Missing video to trim");
    NSError *error = nil;
    AVAssetReader *reader = [[AVAssetReader alloc] initWithAsset:source error:&error];
    if (!reader)
        fail(error.description);
    AVAssetReaderTrackOutput *output =
        [AVAssetReaderTrackOutput assetReaderTrackOutputWithTrack:track outputSettings:nil];
    output.alwaysCopiesSampleData = NO;
    [reader addOutput:output];
    AVAssetWriter *writer = [[AVAssetWriter alloc] initWithURL:[NSURL fileURLWithPath:outPath]
                                                      fileType:AVFileTypeMPEG4
                                                         error:&error];
    if (!writer)
        fail(error.description);
    writer.shouldOptimizeForNetworkUse = YES;
    AVAssetWriterInput *input =
        [AVAssetWriterInput assetWriterInputWithMediaType:AVMediaTypeVideo
                                           outputSettings:nil
                                         sourceFormatHint:(__bridge CMFormatDescriptionRef)
                                                              track.formatDescriptions.firstObject];
    [writer addInput:input];
    if (![writer startWriting] || ![reader startReading])
        fail(writer.error.description ?: reader.error.description);
    [writer startSessionAtSourceTime:kCMTimeZero];
    CMSampleBufferRef sample;
    int seen = 0, written = 0;
    BOOL startSync = NO;
    while ((sample = [output copyNextSampleBuffer])) {
        @autoreleasepool {
            if (CMSampleBufferGetNumSamples(sample) == 0) {
                CFRelease(sample);
                continue;
            }
            int index = seen++;
            if (index < skipFrames || index >= skipFrames + frames) {
                CFRelease(sample);
                continue;
            }
            double pts = CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(sample));
            if (fabs(pts - (double)index / fps) > 1e-6)
                fail(@"Source timestamps are not exact CFR during trim");
            if (written == 0) {
                NSArray *attachments =
                    (__bridge NSArray *)CMSampleBufferGetSampleAttachmentsArray(sample, NO);
                startSync = ![[attachments.firstObject
                    objectForKey:(__bridge NSString *)kCMSampleAttachmentKey_NotSync] boolValue];
                if (!startSync)
                    fail(@"Preroll endpoint is not a sync frame; refusing a non-independent loop");
            }
            CMItemCount n = 0;
            CMSampleBufferGetSampleTimingInfoArray(sample, 0, NULL, &n);
            CMSampleTimingInfo *timings = malloc(sizeof(CMSampleTimingInfo) * n);
            CMSampleBufferGetSampleTimingInfoArray(sample, n, timings, &n);
            for (CMItemCount i = 0; i < n; i++) {
                timings[i].presentationTimeStamp =
                    CMTimeSubtract(timings[i].presentationTimeStamp, CMTimeMake(skipFrames, fps));
                if (CMTIME_IS_VALID(timings[i].decodeTimeStamp))
                    timings[i].decodeTimeStamp =
                        CMTimeSubtract(timings[i].decodeTimeStamp, CMTimeMake(skipFrames, fps));
            }
            CMSampleBufferRef shifted = NULL;
            OSStatus status = CMSampleBufferCreateCopyWithNewTiming(kCFAllocatorDefault, sample, n,
                                                                    timings, &shifted);
            free(timings);
            CFRelease(sample);
            if (status != noErr)
                fail(@"Cannot shift compressed frame timestamps");
            ready(input, writer);
            BOOL ok = [input appendSampleBuffer:shifted];
            CFRelease(shifted);
            if (!ok)
                fail(writer.error.description);
            written++;
        }
    }
    if (reader.status != AVAssetReaderStatusCompleted || written != frames)
        fail(@"Incomplete compressed trim");
    [input markAsFinished];
    [writer endSessionAtSourceTime:CMTimeMake(frames, fps)];
    finish(writer);
    json(
        @{
            @"ok" : @YES,
            @"source" : sourcePath,
            @"file" : outPath,
            @"skipped_preroll_frames" : @(skipFrames),
            @"frames" : @(written),
            @"start_is_sync_frame" : @(startSync),
            @"video_passthrough" : @YES
        },
        nil);
}
static void compose(NSString *videoPath, NSString *audioPath, NSString *outPath, int repeats) {
    fresh(outPath);
    if (repeats < 1)
        fail(@"Repeats must be positive");
    AVURLAsset *video = asset(videoPath);
    AVAssetTrack *original = [video tracksWithMediaType:AVMediaTypeVideo].firstObject;
    if (!original)
        fail(@"Missing video track");
    AVMutableComposition *composition = [AVMutableComposition composition];
    AVMutableCompositionTrack *picture =
        [composition addMutableTrackWithMediaType:AVMediaTypeVideo
                                 preferredTrackID:kCMPersistentTrackID_Invalid];
    picture.preferredTransform = original.preferredTransform;
    NSError *error = nil;
    CMTime cycle = original.timeRange.duration, total = CMTimeMultiply(cycle, repeats);
    AVURLAsset *originalAudio = nil;
    AVAssetTrack *originalSound = nil;
    for (int i = 0; i < repeats; i++)
        if (![picture insertTimeRange:CMTimeRangeMake(original.timeRange.start, cycle)
                              ofTrack:original
                               atTime:CMTimeMultiply(cycle, i)
                                error:&error])
            fail(error.description);
    if (![audioPath isEqualToString:@"-"]) {
        AVURLAsset *sound = asset(audioPath);
        AVAssetTrack *track = [sound tracksWithMediaType:AVMediaTypeAudio].firstObject;
        originalAudio = sound;
        originalSound = track;
        if (!track || fabs(CMTimeGetSeconds(track.timeRange.duration) - CMTimeGetSeconds(total)) >
                          1.0 / 48000)
            fail(@"Audio master must exactly match the requested picture duration");
        if (CMFormatDescriptionGetMediaSubType(
                (__bridge CMFormatDescriptionRef)track.formatDescriptions.firstObject) !=
            kAudioFormatLinearPCM)
            fail(@"Mux requires a lossless PCM source WAV; audio is encoded once during muxing");
        AVMutableCompositionTrack *mix =
            [composition addMutableTrackWithMediaType:AVMediaTypeAudio
                                     preferredTrackID:kCMPersistentTrackID_Invalid];
        if (![mix insertTimeRange:CMTimeRangeMake(kCMTimeZero, total)
                          ofTrack:track
                           atTime:kCMTimeZero
                            error:&error])
            fail(error.description);
    }
    // Copy the already encoded picture and encode lossless PCM to AAC once.
    // Importing AAC through this host's passthrough composition shortened its
    // edit list by 2112 samples; encoding PCM inside the mux avoids that error.
    AVAssetWriter *writer = [[AVAssetWriter alloc] initWithURL:[NSURL fileURLWithPath:outPath]
                                                      fileType:AVFileTypeMPEG4
                                                         error:&error];
    if (!writer)
        fail(error.description);
    writer.shouldOptimizeForNetworkUse = YES;
    NSMutableArray *pairs = [NSMutableArray array], *readers = [NSMutableArray array];
    for (AVAssetTrack *track in composition.tracks) {
        // Read the PCM sound master directly; the picture comes from the exact
        // repeated composition and is copied without a second image encode.
        BOOL isAudio = [track.mediaType isEqualToString:AVMediaTypeAudio];
        AVAsset *readAsset = isAudio ? originalAudio : composition;
        AVAssetTrack *readTrack = isAudio ? originalSound : track;
        AVAssetReader *reader = [[AVAssetReader alloc] initWithAsset:readAsset error:&error];
        if (!reader)
            fail(error.description);
        [readers addObject:reader];
        NSDictionary *readSettings = isAudio ? @{
            AVFormatIDKey : @(kAudioFormatLinearPCM),
            AVLinearPCMBitDepthKey : @16,
            AVLinearPCMIsFloatKey : @NO,
            AVLinearPCMIsBigEndianKey : @NO,
            AVLinearPCMIsNonInterleaved : @NO
        }
                                             : nil;
        AVAssetReaderTrackOutput *output =
            [AVAssetReaderTrackOutput assetReaderTrackOutputWithTrack:readTrack
                                                       outputSettings:readSettings];
        output.alwaysCopiesSampleData = NO;
        [reader addOutput:output];
        CMFormatDescriptionRef format =
            (__bridge CMFormatDescriptionRef)readTrack.formatDescriptions.firstObject;
        NSDictionary *writeSettings = isAudio ? @{
            AVFormatIDKey : @(kAudioFormatMPEG4AAC),
            AVSampleRateKey : @48000,
            AVNumberOfChannelsKey : @2,
            AVEncoderBitRateKey : @256000
        }
                                              : nil;
        AVAssetWriterInput *input =
            [AVAssetWriterInput assetWriterInputWithMediaType:track.mediaType
                                               outputSettings:writeSettings
                                             sourceFormatHint:isAudio ? NULL : format];
        input.expectsMediaDataInRealTime = NO;
        if ([track.mediaType isEqualToString:AVMediaTypeVideo])
            input.transform = track.preferredTransform;
        [writer addInput:input];
        [pairs addObject:@[ output, input ]];
    }
    if (![writer startWriting])
        fail(writer.error.description);
    for (AVAssetReader *reader in readers)
        if (![reader startReading])
            fail(reader.error.description);
    [writer startSessionAtSourceTime:kCMTimeZero];
    dispatch_group_t group = dispatch_group_create();
    for (NSArray *pair in pairs) {
        AVAssetReaderTrackOutput *output = pair[0];
        AVAssetWriterInput *input = pair[1];
        dispatch_group_enter(group);
        dispatch_queue_t queue =
            dispatch_queue_create("ambiance.compressed-track", DISPATCH_QUEUE_SERIAL);
        __block BOOL done = NO;
        [input requestMediaDataWhenReadyOnQueue:queue
                                     usingBlock:^{
                                       if (done)
                                           return;
                                       while (input.readyForMoreMediaData) {
                                           @autoreleasepool {
                                               CMSampleBufferRef sample =
                                                   [output copyNextSampleBuffer];
                                               if (!sample) {
                                                   done = YES;
                                                   [input markAsFinished];
                                                   dispatch_group_leave(group);
                                                   return;
                                               }
                                               // Reader control buffers (DrainAfterDecoding /
                                               // EmptyMedia) are not media packets and are not
                                               // copied into the output.
                                               if (CMSampleBufferGetNumSamples(sample) == 0) {
                                                   CFRelease(sample);
                                                   continue;
                                               }
                                               BOOL ok = [input appendSampleBuffer:sample];
                                               CFRelease(sample);
                                               if (!ok)
                                                   fail(writer.error.description
                                                            ?: @"Compressed sample append failed");
                                           }
                                       }
                                     }];
    }
    dispatch_group_wait(group, DISPATCH_TIME_FOREVER);
    for (AVAssetReader *reader in readers)
        if (reader.status != AVAssetReaderStatusCompleted)
            fail(reader.error.description ?: @"Compressed source read incomplete");
    finish(writer);
    json(
        @{
            @"ok" : @YES,
            @"file" : outPath,
            @"repeats" : @(repeats),
            @"seconds" : @(CMTimeGetSeconds(total)),
            @"video_passthrough" : @YES,
            @"audio" : audioPath,
            @"audio_encoding" : @"PCM source encoded once to AAC stereo 48kHz 256kbps during mux"
        },
        nil);
}
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
static void wavHeader(FILE *file, uint32_t bytes, uint32_t rate, uint16_t channels) {
    uint32_t chunk = bytes + 36, fmt = 16, byteRate = rate * channels * 2;
    uint16_t pcm = 1, align = channels * 2, bits = 16;
    rewind(file);
    fwrite("RIFF", 1, 4, file);
    fwrite(&chunk, 4, 1, file);
    fwrite("WAVEfmt ", 1, 8, file);
    fwrite(&fmt, 4, 1, file);
    fwrite(&pcm, 2, 1, file);
    fwrite(&channels, 2, 1, file);
    fwrite(&rate, 4, 1, file);
    fwrite(&byteRate, 4, 1, file);
    fwrite(&align, 2, 1, file);
    fwrite(&bits, 2, 1, file);
    fwrite("data", 1, 4, file);
    fwrite(&bytes, 4, 1, file);
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
static void verify(NSString *path, int width, int height, int fps, int expectedFrames,
                   int expectedAudio, NSString *reportPath, NSString *framesPath, int loopFrames,
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
    NSMutableDictionary *audio = [NSMutableDictionary dictionaryWithDictionary:@{
        @"tracks" : @(sounds.count),
        @"fully_decoded" : @YES
    }];
    if (sounds.count) {
        AVAssetTrack *sound = sounds.firstObject;
        AVAssetReader *ar = [[AVAssetReader alloc] initWithAsset:source error:&error];
        AVAssetReaderTrackOutput *ao =
            [AVAssetReaderTrackOutput assetReaderTrackOutputWithTrack:sound
                                                       outputSettings:@{
                                                           AVFormatIDKey : @(kAudioFormatLinearPCM),
                                                           AVLinearPCMBitDepthKey : @16,
                                                           AVLinearPCMIsFloatKey : @NO,
                                                           AVLinearPCMIsBigEndianKey : @NO,
                                                           AVLinearPCMIsNonInterleaved : @NO
                                                       }];
        [ar addOutput:ao];
        if (![ar startReading])
            fail(ar.error.description);
        long long raw = 0, presented = 0;
        double first = INFINITY, end = 0, previousAudio = -INFINITY;
        BOOL audioOrdered = YES, audioContiguous = YES;
        double presentedEnd = 0, maxCoverageError = 0;
        double rate = 0;
        int channels = 0;
        double peak = 0, sumSq = 0;
        long long values = 0;
        NSString *wavPath = [framesPath isEqualToString:@"-"]
                                ? nil
                                : [framesPath stringByAppendingPathComponent:@"decoded-audio.wav"];
        FILE *wav = wavPath ? fopen(wavPath.fileSystemRepresentation, "wb") : NULL;
        if (wavPath && !wav)
            fail(@"Cannot open decoded PCM output");
        uint32_t wavBytes = 0;
        if (wav)
            wavHeader(wav, 0, 48000, 2);
        while ((sample = [ao copyNextSampleBuffer])) {
            @autoreleasepool {
                const AudioStreamBasicDescription *fmt =
                    CMAudioFormatDescriptionGetStreamBasicDescription(
                        CMSampleBufferGetFormatDescription(sample));
                rate = fmt->mSampleRate;
                channels = fmt->mChannelsPerFrame;
                long n = CMSampleBufferGetNumSamples(sample);
                double start = CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(sample));
                double stop = start + (double)n / rate;
                if (start < previousAudio - 1e-8)
                    audioOrdered = NO;
                previousAudio = start;
                first = fmin(first, start);
                end = fmax(end, stop);
                raw += n;
                double intendedEnd = (double)expectedFrames / fps;
                long from = (long)fmax(0, ceil(-start * rate - 1e-6)),
                     to = (long)fmin(n, floor((intendedEnd - start) * rate + 1e-6));
                if (to > from) {
                    double coverageStart = start + (double)from / rate,
                           coverageEnd = start + (double)to / rate;
                    double gap = fabs(coverageStart - presentedEnd);
                    maxCoverageError = fmax(maxCoverageError, gap);
                    if (gap > 1.0 / rate + 1e-8)
                        audioContiguous = NO;
                    presentedEnd = coverageEnd;
                    presented += to - from;
                }
                CMBlockBufferRef block = CMSampleBufferGetDataBuffer(sample);
                if (!block)
                    fail(@"Decoded PCM buffer is unavailable");
                size_t len = CMBlockBufferGetDataLength(block);
                if (len < (size_t)n * channels * 2)
                    fail(@"Decoded PCM buffer is truncated");
                int16_t *pcm = malloc(len);
                if (!pcm)
                    fail(@"Decoded PCM allocation failed");
                if (CMBlockBufferCopyDataBytes(block, 0, len, pcm) != kCMBlockBufferNoErr)
                    fail(@"Decoded PCM copy failed");
                {
                    for (long i = from * channels; i < to * channels; i++) {
                        double v = pcm[i] / 32768.0;
                        peak = fmax(peak, fabs(v));
                        sumSq += v * v;
                        values++;
                    }
                    if (wav && to > from) {
                        uint32_t countBytes = (uint32_t)(to - from) * channels * 2;
                        if (fwrite(pcm + from * channels, 1, countBytes, wav) != countBytes)
                            fail(@"Decoded PCM save failed");
                        wavBytes += countBytes;
                    }
                }
                free(pcm);
                CFRelease(sample);
            }
        }
        if (wav) {
            wavHeader(wav, wavBytes, (uint32_t)rate, (uint16_t)channels);
            fclose(wav);
            audio[@"decoded_wav"] = wavPath;
        }
        NSMutableArray *segments = [NSMutableArray array];
        for (AVAssetTrackSegment *segment in sound.segments) {
            CMTimeMapping m = segment.timeMapping;
            [segments addObject:@{
                @"empty" : @(segment.empty),
                @"source_start" : @(CMTimeGetSeconds(m.source.start)),
                @"source_duration" : @(CMTimeGetSeconds(m.source.duration)),
                @"target_start" : @(CMTimeGetSeconds(m.target.start)),
                @"target_duration" : @(CMTimeGetSeconds(m.target.duration))
            }];
        }
        audio[@"track_segments"] = segments;
        audio[@"contiguous_presented_samples"] = @(audioContiguous);
        audio[@"max_presented_coverage_error_seconds"] = @(maxCoverageError);
        audio[@"presented_end_seconds"] = @(presentedEnd);
        audio[@"fully_decoded"] = @(ar.status == AVAssetReaderStatusCompleted);
        audio[@"monotonic_timestamps"] = @(audioOrdered);
        audio[@"raw_decoded_samples"] = @(raw);
        audio[@"presented_samples"] = @(presented);
        audio[@"sample_rate"] = @(rate);
        audio[@"channels"] = @(channels);
        audio[@"first_decoded_pts"] = @(first);
        audio[@"last_decoded_end"] = @(end);
        audio[@"track_start"] = @(CMTimeGetSeconds(sound.timeRange.start));
        audio[@"track_duration"] = @(CMTimeGetSeconds(sound.timeRange.duration));
        audio[@"peak_dbfs"] = @(20 * log10(fmax(peak, 1e-12)));
        audio[@"rms_dbfs"] = @(20 * log10(fmax(sqrt(sumSq / fmax(values, 1)), 1e-12)));
        audio[@"presentation_method"] =
            @"AVAssetReader decoded sample timestamps and lengths are counted only inside [0, expected duration). Track edit segments and raw decoded count are reported separately; the rendered PCM is retained for comparison against the source WAV.";
    }
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
static NSString *dataHash(NSData *data) {
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(data.bytes, (CC_LONG)data.length, digest);
    NSMutableString *text = [NSMutableString stringWithCapacity:64];
    for (int i = 0; i < CC_SHA256_DIGEST_LENGTH; i++)
        [text appendFormat:@"%02x", digest[i]];
    return text;
}
static void probePicture(NSString *path) {
    AVURLAsset *source = asset(path);
    NSArray *videos = [source tracksWithMediaType:AVMediaTypeVideo],
            *sounds = [source tracksWithMediaType:AVMediaTypeAudio];
    if (videos.count != 1)
        fail(@"Expected exactly one encoded video track");
    AVAssetTrack *track = videos.firstObject;
    CMFormatDescriptionRef format =
        (__bridge CMFormatDescriptionRef)track.formatDescriptions.firstObject;
    FourCharCode codec = CMFormatDescriptionGetMediaSubType(format);
    char codecName[5] = {(char)(codec >> 24), (char)(codec >> 16), (char)(codec >> 8), (char)codec,
                         0};
    int fps = (int)llround(track.nominalFrameRate);
    NSMutableArray *errors = [NSMutableArray array], *samples = [NSMutableArray array];
    if (codec != kCMVideoCodecType_H264)
        [errors addObject:@"Only H.264 compressed picture is supported"];
    if (fps < 1 || fabs(track.nominalFrameRate - fps) > 1e-6)
        [errors addObject:@"Only positive integer constant frame rates are supported"];
    if (!CGAffineTransformIsIdentity(track.preferredTransform))
        [errors
            addObject:
                @"Transformed video tracks are unsupported; provide a picture with its final raster orientation"];
    NSError *error = nil;
    AVAssetReader *reader = [[AVAssetReader alloc] initWithAsset:source error:&error];
    if (!reader)
        fail(error.description);
    AVAssetReaderTrackOutput *output =
        [AVAssetReaderTrackOutput assetReaderTrackOutputWithTrack:track outputSettings:nil];
    [reader addOutput:output];
    if (![reader startReading])
        fail(reader.error.description);
    CMSampleBufferRef sample;
    int count = 0;
    double maxTimingError = 0, lastEnd = 0;
    BOOL firstSync = NO;
    while ((sample = [output copyNextSampleBuffer])) {
        @autoreleasepool {
            CMItemCount n = CMSampleBufferGetNumSamples(sample);
            if (!n) {
                CFRelease(sample);
                continue;
            }
            if (n != 1)
                fail(@"Expected one encoded video sample per packet");
            double pts = CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(sample)),
                   duration = CMTimeGetSeconds(CMSampleBufferGetDuration(sample));
            if (!isfinite(pts))
                fail(@"Invalid compressed picture timestamp");
            if (fps > 0)
                maxTimingError = fmax(maxTimingError, fabs(pts - (double)count / fps));
            lastEnd =
                pts + (isfinite(duration) && duration > 0 ? duration : (fps > 0 ? 1.0 / fps : 0));
            NSArray *attachments =
                (__bridge NSArray *)CMSampleBufferGetSampleAttachmentsArray(sample, NO);
            BOOL sync = ![[attachments.firstObject
                objectForKey:(__bridge NSString *)kCMSampleAttachmentKey_NotSync] boolValue];
            if (count == 0)
                firstSync = sync;
            CMBlockBufferRef block = CMSampleBufferGetDataBuffer(sample);
            if (!block)
                fail(@"Missing encoded picture payload");
            size_t length = CMBlockBufferGetDataLength(block);
            NSMutableData *payload = [NSMutableData dataWithLength:length];
            if (CMBlockBufferCopyDataBytes(block, 0, length, payload.mutableBytes) !=
                kCMBlockBufferNoErr)
                fail(@"Cannot read encoded picture payload");
            [samples addObject:@{
                @"frame" : @(count),
                @"pts" : @(pts),
                @"bytes" : @(length),
                @"sha256" : dataHash(payload),
                @"sync" : @(sync)
            }];
            count++;
            CFRelease(sample);
        }
    }
    if (reader.status != AVAssetReaderStatusCompleted)
        fail(reader.error.description ?: @"Incomplete compressed picture inspection");
    double expected = fps > 0 ? (double)count / fps : 0;
    if (!count || !firstSync || maxTimingError > 1e-6 ||
        fabs(CMTimeGetSeconds(track.timeRange.start)) > 1e-6 ||
        fabs(CMTimeGetSeconds(track.timeRange.duration) - expected) > 1e-6 ||
        fabs(lastEnd - expected) > 1e-6)
        [errors
            addObject:
                @"Picture must begin at zero on a sync frame with exact CFR timestamps and duration"];
    json(
        @{
            @"ok" : @YES,
            @"supported_cfr_h264" : @(errors.count == 0),
            @"errors" : errors,
            @"file" : path,
            @"codec" : @(codecName),
            @"width" : @(track.naturalSize.width),
            @"height" : @(track.naturalSize.height),
            @"fps" : @(fps),
            @"frames" : @(count),
            @"duration_seconds" : @(CMTimeGetSeconds(track.timeRange.duration)),
            @"video_tracks" : @(videos.count),
            @"audio_tracks" : @(sounds.count),
            @"samples" : samples
        },
        nil);
}
int main(int argc, const char **argv) {
    @autoreleasepool {
        if (argc == 3 && !strcmp(argv[1], "packets")) {
            AVURLAsset *a = asset(@(argv[2]));
            AVAssetTrack *t = [a tracksWithMediaType:AVMediaTypeAudio].firstObject;
            NSError *e = nil;
            AVAssetReader *r = [[AVAssetReader alloc] initWithAsset:a error:&e];
            AVAssetReaderTrackOutput *o =
                [AVAssetReaderTrackOutput assetReaderTrackOutputWithTrack:t outputSettings:nil];
            [r addOutput:o];
            [r startReading];
            CMSampleBufferRef s;
            int n = 0;
            NSMutableArray *items = [NSMutableArray array];
            while ((s = [o copyNextSampleBuffer])) {
                NSDictionary *att = CFBridgingRelease(CMCopyDictionaryOfAttachments(
                    kCFAllocatorDefault, s, kCMAttachmentMode_ShouldPropagate));
                NSDictionary *item = @{
                    @"index" : @(n),
                    @"pts" : [NSString
                        stringWithFormat:@"%g", CMTimeGetSeconds(
                                                    CMSampleBufferGetPresentationTimeStamp(s))],
                    @"duration" : [NSString
                        stringWithFormat:@"%g", CMTimeGetSeconds(CMSampleBufferGetDuration(s))],
                    @"samples" : @(CMSampleBufferGetNumSamples(s)),
                    @"attachments" : att.description ?: @""
                };
                if (n < 3)
                    [items addObject:item];
                else if (items.count == 6) {
                    [items removeObjectAtIndex:3];
                    [items addObject:item];
                } else
                    [items addObject:item];
                CFRelease(s);
                n++;
            }
            json(@{@"count" : @(n), @"packets" : items}, nil);
        } else if (argc == 3 && !strcmp(argv[1], "probe-picture"))
            probePicture(@(argv[2]));
        else if (argc == 3 && !strcmp(argv[1], "inspect")) {
            AVURLAsset *a = asset(@(argv[2]));
            NSMutableArray *tracks = [NSMutableArray array];
            for (AVAssetTrack *t in a.tracks) {
                NSMutableArray *segments = [NSMutableArray array];
                for (AVAssetTrackSegment *s in t.segments) {
                    CMTimeMapping m = s.timeMapping;
                    [segments addObject:@{
                        @"source_start" : @(CMTimeGetSeconds(m.source.start)),
                        @"source_duration" : @(CMTimeGetSeconds(m.source.duration)),
                        @"target_start" : @(CMTimeGetSeconds(m.target.start)),
                        @"target_duration" : @(CMTimeGetSeconds(m.target.duration))
                    }];
                }
                [tracks addObject:@{
                    @"type" : t.mediaType,
                    @"start" : @(CMTimeGetSeconds(t.timeRange.start)),
                    @"duration" : @(CMTimeGetSeconds(t.timeRange.duration)),
                    @"segments" : segments
                }];
            }
            json(@{@"duration" : @(CMTimeGetSeconds(a.duration)), @"tracks" : tracks}, nil);
        } else if ((argc == 9 || argc == 10) && !strcmp(argv[1], "encode"))
            encode(@(argv[2]), atoi(argv[3]), atoi(argv[4]), atoi(argv[5]), atoi(argv[6]),
                   atoi(argv[7]), argc == 10 ? atoi(argv[9]) : atoi(argv[5]) * 2);
        else if (argc == 7 && !strcmp(argv[1], "trim"))
            trimPicture(@(argv[2]), @(argv[3]), atoi(argv[4]), atoi(argv[5]), atoi(argv[6]));
        else if (argc == 4 && !strcmp(argv[1], "audio"))
            encodeAudio(@(argv[2]), @(argv[3]));
        else if (argc == 6 && !strcmp(argv[1], "compose"))
            compose(@(argv[2]), @(argv[3]), @(argv[4]), atoi(argv[5]));
        else if ((argc == 10 || argc == 11 || argc == 12) && !strcmp(argv[1], "verify")) {
            int loop = argc >= 11 ? atoi(argv[10]) : atoi(argv[6]);
            if (loop < 1 || atoi(argv[5]) < 1 || atoi(argv[6]) < 1)
                fail(@"Invalid expected frame timing");
            verify(@(argv[2]), atoi(argv[3]), atoi(argv[4]), atoi(argv[5]), atoi(argv[6]),
                   atoi(argv[7]), @(argv[8]), @(argv[9]), loop, argc == 12 ? @(argv[11]) : @"");
        } else {
            fprintf(
                stderr,
                "Usage: media encode OUTPUT WIDTH HEIGHT FPS FRAMES BITRATE rgba [KEY_INTERVAL]\n       media trim INPUT.mp4 OUTPUT.mp4 SKIP_FRAMES FRAMES FPS\n       media audio INPUT.wav OUTPUT.m4a\n       media compose VIDEO.mp4 AUDIO.wav-or-- OUTPUT.mp4 REPEATS\n       media verify VIDEO WIDTH HEIGHT FPS FRAMES AUDIO_TRACKS REPORT.json CONTACT_DIR-or-- [LOOP_FRAMES] [CONTACT_FRAME_CSV]\n");
            return 2;
        }
        return 0;
    }
}
