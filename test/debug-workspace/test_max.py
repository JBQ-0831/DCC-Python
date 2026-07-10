def simple_test():
    for i in range(10):
        print(i)


def rt_test():
    try:
        from pymxs import runtime as rt
        print("rt module is available")
        for o in rt.objects:
            print(o)
        # print(rt.objects)

    except ImportError:
        print("rt module is not available")

if __name__ == "__main__":
    simple_test()
    rt_test()