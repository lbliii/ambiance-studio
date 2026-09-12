#pragma once
#import <AVFoundation/AVFoundation.h>

NSDictionary *verifyAudio(AVURLAsset *source, NSArray *sounds, int expectedFrames, int fps,
                          NSString *framesPath);
