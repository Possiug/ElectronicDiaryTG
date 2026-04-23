from datetime import datetime as DT
from ansi_escape_seq import *


class Logger:
    intendention = 0
    name = ''
    color_mode = False
    time_format = "%Y-%m-%d %H:%M:%S"

    
    def __init__(self, name: str, color_mode: bool = None, time_format: str = None):
        self.name = name
        if (color_mode is None):
            print("Testing color mode support...")
            Graphics.foreground_256_color(1)
            print("This line must be red. If it isn't red, you should disable color mode!")
            Graphics.reset()
            print()
            q = input("Enable color mode? (1 - enable, other keys - disable): ")
            if (q == '1'):
                self.color_mode = True
                Graphics.foreground_256_color(2)
                print("Color mode enabled!")
                Graphics.reset()
            else:
                print("Color mode disabled!")
        else:
            self.color_mode = color_mode
        if (time_format is not None):
            self.time_format = time_format


    def write(self, log_type: str, text: str, color: int = None):
        if (color is not None and self.color_mode):
            Graphics.foreground_256_color(color)
        print(f"[{DT.now().strftime(self.time_format)}]" + '  ' * self.intendention + f" [{self.name}/{log_type}] " + text)
        if (color is not None and self.color_mode):
            Graphics.color_8_16(39)


    


    def log(self, text=""):
        self.write("LOG", text, 245)


    def info(self, text=""):
        self.write("INFO", text, 81)


    def warn(self, text=""):
        self.write("WARN", text, 208)


    def error(self, text=""):
        self.write("ERROR", text, 196)


    def handle_error(self, e: Exception):
        self.error(f"Exception {type(e)}")
        self.error(str(e))
    

    def nopre(self, text=""):
        print('  ' * self.intendention + f"    " + text)


    def fin(self):
        self.intendention += 1
    

    def fout(self):
        self.intendention -= 1
        if (self.intendention < 0):
            self.intendention = 0
