"""
File used for tesing/debugging various features
"""


def main():
    print(__file__)
    print(__name__)
    for i in range(10):
        print(i)
    import substance_painter.project as sp_project
    print(sp_project.is_open())
if __name__ == "__main__":
    main()
