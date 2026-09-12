#pragma once
#import <Foundation/Foundation.h>
#import <AVFoundation/AVFoundation.h>

void fail(NSString *message);
void fresh(NSString *path);
AVURLAsset *asset(NSString *path);
void json(NSDictionary *value, NSString *path);
void finish(AVAssetWriter *writer);
void ready(AVAssetWriterInput *input, AVAssetWriter *writer);
