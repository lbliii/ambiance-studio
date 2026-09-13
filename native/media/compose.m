#import "media_common.h"
#import "media_commands.h"
#include <math.h>

void trimPicture(NSString *sourcePath, NSString *outPath, int skipFrames, int frames, int fps) {
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
static NSDictionary *audioCapability(int bitrate) {
    if (bitrate != 256000 && bitrate != 320000 && bitrate != 384000)
        fail(@"Unsupported stereo AAC bitrate; choose 256000, 320000 or 384000 bps (no fallback)");
    AVAudioFormat *input = [[AVAudioFormat alloc] initWithCommonFormat:AVAudioPCMFormatFloat32
        sampleRate:48000 channels:2 interleaved:YES];
    AVAudioFormat *output = [[AVAudioFormat alloc] initWithSettings:@{AVFormatIDKey:@(kAudioFormatMPEG4AAC),
        AVSampleRateKey:@48000, AVNumberOfChannelsKey:@2}];
    AVAudioConverter *converter = [[AVAudioConverter alloc] initFromFormat:input toFormat:output];
    NSArray *rates = converter.applicableEncodeBitRates;
    if (!converter || !rates.count) fail(@"AAC format-specific bitrate capability unavailable; media-service access is required");
    if (![rates containsObject:@(bitrate)])
        fail([NSString stringWithFormat:@"Requested AAC bitrate %d is unsupported for stereo 48 kHz on this backend; applicable rates %@; no fallback", bitrate, rates]);
    return @{@"ok":@YES, @"codec":@"aac", @"sample_rate":@48000, @"channels":@2,
        @"bitrate_bps":@(bitrate), @"applicable_bitrates_bps":rates,
        @"bitrate_strategy":converter.bitRateStrategy ?: @"backend default",
        @"backend":@"macOS AVFoundation", @"os_version":NSProcessInfo.processInfo.operatingSystemVersionString,
        @"method":@"AVAudioConverter applicableEncodeBitRates for actual stereo 48 kHz formats; capability check, not an encode/decode pass"};
}
NSDictionary *audioEncodingSettings(int bitrate) {
    audioCapability(bitrate);
    return @{AVFormatIDKey : @(kAudioFormatMPEG4AAC), AVSampleRateKey : @48000,
             AVNumberOfChannelsKey : @2, AVEncoderBitRateKey : @(bitrate)};
}
void audioPreflight(int bitrate) {
    json(audioCapability(bitrate), nil);
}
void compose(NSString *videoPath, NSString *audioPath, NSString *outPath, int repeats, int audioBitrate) {
    NSDictionary *audioSettings = [audioPath isEqualToString:@"-"] ? nil : audioEncodingSettings(audioBitrate);
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
            AVLinearPCMBitDepthKey : @32,
            AVLinearPCMIsFloatKey : @YES,
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
        NSDictionary *writeSettings = isAudio ? audioSettings : nil;
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
            @"audio_encoding" : [audioPath isEqualToString:@"-"] ? (id)[NSNull null] : @{
                @"codec":@"aac", @"sample_rate":@48000, @"channels":@2, @"bitrate_bps":@(audioBitrate),
                @"backend":@"macOS AVFoundation", @"os_version":NSProcessInfo.processInfo.operatingSystemVersionString,
                @"input_decode":@"float32 PCM; encoded once during mux; no gain or normalization"}
        },
        nil);
}
