#import "media_common.h"
#import "verify_audio.h"
#include <math.h>

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
NSDictionary *verifyAudio(AVURLAsset *source, NSArray *sounds, int expectedFrames, int fps,
                          NSString *framesPath) {
    NSError *error = nil;
    CMSampleBufferRef sample;
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
    return audio;
}
