#import "media_common.h"
#include <unistd.h>

void fail(NSString *message) {
    fprintf(stderr, "%s\n", message.UTF8String);
    exit(1);
}
void fresh(NSString *path) {
    if ([[NSFileManager defaultManager] fileExistsAtPath:path])
        fail([@"Refusing to overwrite: " stringByAppendingString:path]);
}
AVURLAsset *asset(NSString *path) {
    if (![[NSFileManager defaultManager] fileExistsAtPath:path])
        fail([@"Missing: " stringByAppendingString:path]);
    return [AVURLAsset URLAssetWithURL:[NSURL fileURLWithPath:path]
                               options:@{
                                   AVURLAssetPreferPreciseDurationAndTimingKey : @YES
                               }];
}
void json(NSDictionary *value, NSString *path) {
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
void finish(AVAssetWriter *writer) {
    dispatch_semaphore_t done = dispatch_semaphore_create(0);
    [writer finishWritingWithCompletionHandler:^{
      dispatch_semaphore_signal(done);
    }];
    dispatch_semaphore_wait(done, DISPATCH_TIME_FOREVER);
    if (writer.status != AVAssetWriterStatusCompleted)
        fail(writer.error.description ?: @"Writer failed");
}
void ready(AVAssetWriterInput *input, AVAssetWriter *writer) {
    while (!input.readyForMoreMediaData) {
        if (writer.status == AVAssetWriterStatusFailed ||
            writer.status == AVAssetWriterStatusCancelled)
            fail(writer.error.description ?: @"Writer stopped");
        usleep(1000);
    }
}
