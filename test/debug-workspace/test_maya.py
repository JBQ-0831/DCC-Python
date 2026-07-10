"""
File used for tesing/debugging various features
"""

from maya import cmds

def main():
    print(123123)
    print(__file__)
    print(__name__)
    for i in range(10):
        print(i)

if __name__ == "__main__":
    main()
