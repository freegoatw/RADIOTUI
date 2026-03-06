import vlc
import time

class Player:
    def __init__(self):
        self.instance = vlc.Instance('--quiet', "--network-caching=2000")
        self.player = self.instance.media_player_new()
    
    def Play(self, url):
        if self.player:
            self.Stop()
        media = self.instance.media_new(url)
        self.player.set_media(media)
        self.player.play()
        count = 0
        while True:
            state = self.player.get_state()
            if state == vlc.State.Opening:
                print("\rConnecting. . .", end="")
            elif state == vlc.State.Buffering:
                print("\rBuffering. . .", end="")
                self.Pause()
            elif state == vlc.State.Playing:
                print("\rPlaying. . .", end="")
                count+=1
                self.player.play()
            elif state == vlc.State.Error:
                print("ERROR")
                self.Stop()
                break
            time.sleep(0.5)
            if count == 10:
                break

    def Pause(self):
        if self.player:
            self.player.pause()
    def Stop(self):
        if self.player:
            self.player.stop()
