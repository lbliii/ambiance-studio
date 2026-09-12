#import "media_common.h"
#import "media_commands.h"
#import <CommonCrypto/CommonDigest.h>
#include <math.h>

static NSString *dataHash(NSData *data) {
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(data.bytes, (CC_LONG)data.length, digest);
    NSMutableString *text = [NSMutableString stringWithCapacity:64];
    for (int i = 0; i < CC_SHA256_DIGEST_LENGTH; i++)
        [text appendFormat:@"%02x", digest[i]];
    return text;
}
void probePicture(NSString *path) {
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

void inspectPackets(NSString *path) {
    AVURLAsset *a = asset(path);
    AVAssetTrack *t = [a tracksWithMediaType:AVMediaTypeAudio].firstObject;
    NSError *e = nil;
    AVAssetReader *r = [[AVAssetReader alloc] initWithAsset:a error:&e];
    AVAssetReaderTrackOutput *o = [AVAssetReaderTrackOutput assetReaderTrackOutputWithTrack:t
                                                                             outputSettings:nil];
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
                stringWithFormat:@"%g",
                                 CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(s))],
            @"duration" :
                [NSString stringWithFormat:@"%g", CMTimeGetSeconds(CMSampleBufferGetDuration(s))],
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
}

void inspectTracks(NSString *path) {
    AVURLAsset *a = asset(path);
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
}
