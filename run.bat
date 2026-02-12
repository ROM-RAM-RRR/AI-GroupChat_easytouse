@echo off
title AI Group Chat System - Running
echo Starting Streamlit interface, please wait...

:: Start the program
streamlit run AI_Chatting_Streamlit.py

:: If the program closes unexpectedly, keep the window to show error messages
pause