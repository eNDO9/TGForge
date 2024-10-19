from telethon import TelegramClient, functions
from telethon.tl.types import (
    MessageMediaDocument,
    MessageMediaPhoto,
    MessageMediaWebPage,
    MessageMediaContact,
)

from telethon.errors import FloodWaitError, RpcCallFailError
import asyncio
from aioconsole import ainput
import re
import time
from collections import Counter
from urllib.parse import urlparse
from datetime import datetime
import time

import socket

import pandas as pd
import os
from docx import Document

import streamlit as st

st.print('TGForge is a cool name')