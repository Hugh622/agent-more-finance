# -*- coding: utf-8 -*-
"""bt_engine — 方法学线回测引擎（P1② 混合模式 logic 承载层 ＋ P2 三规则族回测）
数据契约：只消费冻结层（manifest_v2_freeze 侧车校验通过的文件），身份由 sha256 认定。
规则契约：逻辑主体全部在本包（rules_*.py），注册册 YAML 只存元数据/参数/版本——
          logic_ref 字符串 bt_engine.<module>::<func> 必须可解析、可调用、有单测。
"""
__version__ = "1.0.0"
