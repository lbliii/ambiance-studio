#pragma once
#import <Foundation/Foundation.h>
#import <AVFoundation/AVFoundation.h>

void encode(NSString *path, int width, int height, int fps, int frames, int bitrate,
            int keyInterval);
void encodeAudio(NSString *sourcePath, NSString *outPath);
void trimPicture(NSString *sourcePath, NSString *outPath, int skipFrames, int frames, int fps);
void compose(NSString *videoPath, NSString *audioPath, NSString *outPath, int repeats);
void verify(NSString *path, int width, int height, int fps, int expectedFrames, int expectedAudio,
            NSString *reportPath, NSString *framesPath, int loopFrames,
            NSString *requestedContacts);
void probePicture(NSString *path);
void inspectPackets(NSString *path);
void inspectTracks(NSString *path);
