def main():
    print(__file__)
    print(__name__)
    for i in range(3):
        print(i)

    from maya import cmds
    cmds.warning("Hello World")

if __name__ == "__main__":
    main()
