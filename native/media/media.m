// Native command dispatch; implementations share only media_common.h helpers.
#import "media_common.h"
#import "media_commands.h"

int main(int argc, const char **argv) {
    @autoreleasepool {
        if (argc == 3 && !strcmp(argv[1], "packets"))
            inspectPackets(@(argv[2]));
        else if (argc == 3 && !strcmp(argv[1], "probe-picture"))
            probePicture(@(argv[2]));
        else if (argc == 3 && !strcmp(argv[1], "inspect"))
            inspectTracks(@(argv[2]));
        else if ((argc == 9 || argc == 10) && !strcmp(argv[1], "encode"))
            encode(@(argv[2]), atoi(argv[3]), atoi(argv[4]), atoi(argv[5]), atoi(argv[6]),
                   atoi(argv[7]), argc == 10 ? atoi(argv[9]) : atoi(argv[5]) * 2);
        else if (argc == 7 && !strcmp(argv[1], "trim"))
            trimPicture(@(argv[2]), @(argv[3]), atoi(argv[4]), atoi(argv[5]), atoi(argv[6]));
        else if ((argc == 4 || argc == 5) && !strcmp(argv[1], "audio"))
            encodeAudio(@(argv[2]), @(argv[3]), argc == 5 ? atoi(argv[4]) : 256000);
        else if (argc == 3 && !strcmp(argv[1], "audio-preflight"))
            audioPreflight(atoi(argv[2]));
        else if ((argc == 6 || argc == 7) && !strcmp(argv[1], "compose"))
            compose(@(argv[2]), @(argv[3]), @(argv[4]), atoi(argv[5]), argc == 7 ? atoi(argv[6]) : 256000);
        else if ((argc == 10 || argc == 11 || argc == 12) && !strcmp(argv[1], "verify")) {
            int loop = argc >= 11 ? atoi(argv[10]) : atoi(argv[6]);
            if (loop < 1 || atoi(argv[5]) < 1 || atoi(argv[6]) < 1)
                fail(@"Invalid expected frame timing");
            verify(@(argv[2]), atoi(argv[3]), atoi(argv[4]), atoi(argv[5]), atoi(argv[6]),
                   atoi(argv[7]), @(argv[8]), @(argv[9]), loop, argc == 12 ? @(argv[11]) : @"");
        } else {
            fprintf(
                stderr,
                "Usage: media encode OUTPUT WIDTH HEIGHT FPS FRAMES BITRATE rgba [KEY_INTERVAL]\n       media trim INPUT.mp4 OUTPUT.mp4 SKIP_FRAMES FRAMES FPS\n       media audio INPUT.wav OUTPUT.m4a [BITRATE]\n       media audio-preflight BITRATE\n       media compose VIDEO.mp4 AUDIO.wav-or-- OUTPUT.mp4 REPEATS [AUDIO_BITRATE]\n       media verify VIDEO WIDTH HEIGHT FPS FRAMES AUDIO_TRACKS REPORT.json CONTACT_DIR-or-- [LOOP_FRAMES] [CONTACT_FRAME_CSV]\n");
            return 2;
        }
        return 0;
    }
}
