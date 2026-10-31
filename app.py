"""Standalone NextTest research workbench."""

import streamlit as st

from nexttest.app.nexttest_ui import render


def main() -> None:
    st.set_page_config(
        page_title="NextTest · 下一次实验怎么选",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    render(st)


if __name__ == "__main__":
    main()
