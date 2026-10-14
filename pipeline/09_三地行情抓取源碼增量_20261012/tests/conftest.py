# -*- coding: utf-8 -*-
"""pytest conftest: 把管道根注入 sys.path, 使 market_fetcher 可导入。"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
