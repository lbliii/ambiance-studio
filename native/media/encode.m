#import "media_common.h"
#import "media_commands.h"
#import <CoreVideo/CoreVideo.h>

void encode(NSString *path, int width, int height, int fps, int frames, int bitrate,
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
void encodeAudio(NSString *sourcePath, NSString *outPath, int bitrate) {
    NSDictionary *settings = audioEncodingSettings(bitrate);
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
                                                       AVLinearPCMBitDepthKey : @32,
                                                       AVLinearPCMIsFloatKey : @YES,
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
                                           outputSettings:settings];
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
            @"bitrate" : @(bitrate),
            @"source_seconds" : @(CMTimeGetSeconds(source.duration))
        },
        nil);
}
