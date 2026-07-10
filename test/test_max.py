def main():
    print(__file__)
    print(__name__)
    for i in range(3):
        print(i)

    from pymxs import runtime as rt
    for o in rt.objects:
        print(o)

if __name__ == "__main__":
    main()