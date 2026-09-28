from .ui.app import App
from .ui.intro import BootScene


def main():
    app = App()
    app.run(BootScene(app))


if __name__ == "__main__":
    main()
