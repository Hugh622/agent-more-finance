# -*- coding: utf-8 -*-
"""框架规则条款库 v1.3（正式15条/模拟3条/待核1条/记账若干）。

版本沿革：
  v1.1（9/27 前基线）→ v1.2（9/27 用户批准收编，15 正式条款）
  → v1.3（9/24 双轮复盘同向验证后升格：C20/C21/C22 强趋势格/F-修/原则章）
  v1.3 即日生效；升級只加紀律不加自由，驗證失敗永久撤回。

条款状态：OFFICIAL=正式生效 / SIM=模拟验证中 / PENDING=待核 / LEDGER=记账。
"""
from dataclasses import dataclass
from enum import Enum
from typing import Final


class ClauseStatus(str, Enum):
    OFFICIAL = "OFFICIAL"
    SIM = "SIM"
    PENDING = "PENDING"
    LEDGER = "LEDGER"


@dataclass(frozen=True)
class Clause:
    code: str
    title: str
    status: ClauseStatus
    body: str
    origin: str


CLAUSES: Final = (
    # --- v1.2 正式 15 条 ---
    Clause("C1", "估值折让检查", ClauseStatus.OFFICIAL,
           "建仓区间须过估值折让：溢价 1SD 仓位×0.5，2SD 只观察", "Buffett B1"),
    Clause("C2", "声明制", ClauseStatus.OFFICIAL,
           "格位＋样本边界声明：答不出「我买什么/不买什么」不落场", "Buffett B2"),
    Clause("C3", "护城河折旧", ClauseStatus.OFFICIAL,
           "「永久」改「有到期日」：护城河剩余年限<5年必挂里程碑", "Buffett B3"),
    Clause("C4", "六分类并入R4", ClauseStatus.OFFICIAL,
           "Lynch 六分类并入催化剂分类，PEG 入 F 分；十倍股期待不采纳", "Lynch"),
    Clause("C5", "波动率分位仓位系数", ClauseStatus.OFFICIAL,
           "按 ATR/波动率分位对标准仓位乘系数（波动率目标制的细则层）", "Minervini/Gerko"),
    Clause("C6", "动量退出", ClauseStatus.OFFICIAL,
           "动量衰减优先于价格破位；RS 衰减先行降档", "Minervini"),
    Clause("C10", "Stage2 过滤器", ClauseStatus.OFFICIAL,
           "只交易 Stage 2 上升趋势结构，Stage 1/3/4 禁新仓", "Minervini"),
    Clause("C11", "止损硬顶", ClauseStatus.OFFICIAL,
           "单笔止损硬顶 -0.92×触发线（防滑点扩大），跳空接受滑点", "Minervini"),
    Clause("C13", "波动率视角环境规则", ClauseStatus.OFFICIAL,
           "VIX 期限结构倒挂=环境降档信号，随 VIX 分位调对冲预算", "新生代"),
    Clause("C14", "基本面三闸之一", ClauseStatus.OFFICIAL,
           "盈利下修通道开启→禁新仓（9月非农大miss后启用逻辑）", "避损规则v1.0"),
    Clause("C15", "基本面三闸之二", ClauseStatus.OFFICIAL,
           "叙事采信分级：席位归因类叙事降级为假设清单，须事件研究验证", "避损规则v1.0"),
    Clause("C16", "基本面三闸之三", ClauseStatus.OFFICIAL,
           "观察面收敛≤3点：防「支撑计数谬误/不可证伪 shake out/F&G 无基准率」", "避损规则v1.0"),
    Clause("C17", "主题仓状态机", ClauseStatus.OFFICIAL,
           "NORMAL≤20% / ALERT≤12% / LATE≤8% / END 0-2%（十信号驱动）", "科技浪潮课题"),
    Clause("C18", "即时闸 T1-T3", ClauseStatus.OFFICIAL,
           "金链 T1：12月加息概率>70%→金5→4%＋矿业清零；<60% 撤销", "FOMC实证"),
    Clause("C19", "爆破剧本", ClauseStatus.OFFICIAL,
           "泡沫爆破后 45 日内反弹按死猫处理；右侧需 ≥53 日＋200DMA 二守分三批", "三轮泡沫回撤 -77~-84%"),
    # --- v1.3 升格条款（9/24 两轮同向） ---
    Clause("C20", "止盈首阻力位定价", ClauseStatus.OFFICIAL,
           "止盈腿按首阻力位定价，不再「赢面接不住」", "9月复盘·介入层2/9"),
    Clause("C21", "动量大闸", ClauseStatus.OFFICIAL,
           "动量失速环境禁左侧抢反弹，等右侧确认", "9月复盘"),
    Clause("C22", "缺口二元对待制", ClauseStatus.OFFICIAL,
           "强趋势格：突破确认＋移动跟随；回调区只留弱势修复格", "早期复盘 HPE 7pp"),
    Clause("C23", "收市口径机器校验", ClauseStatus.OFFICIAL,
           "执行线核验以收市口径机器校验（02269 快照硬伤修复）", "02269 判例"),
    Clause("C24", "假突破次日收复再确认白名单", ClauseStatus.OFFICIAL,
           "假突破次日收复再确认白名单制（HPE +7pp 案例）", "早期复盘"),
    Clause("F-修", "利率敏感性强制评级", ClauseStatus.OFFICIAL,
           "每标的强制标利率敏感度（10Y>5.05% 环境下的准入参数）", "9月复盘"),
    # --- 模拟 3 条 ---
    Clause("C7", "PEAD 漂移", ClauseStatus.SIM,
           "财报后漂移模拟（whipsaw 缓解后先启 C7 模拟）", "新生代"),
    Clause("C9", "13D 跟踪", ClauseStatus.SIM,
           "13D/F 大额持仓跟踪模拟", "新生代"),
    Clause("C12", "收缩突破触发器", ClauseStatus.SIM,
           "波动收缩→突破触发器（Gerko 视角挂载）", "新生代"),
    # --- 待核 1 条 ---
    Clause("C8", "CTA 对冲腿", ClauseStatus.PENDING,
           "CTA 趋势跟随作对冲腿，待 SG Trend 官方数据核实", "Gerko"),
    # --- 记账 ---
    Clause("D-1", "十信号 v2（G类循环融资2.0＋卖水人降级＋数据/价格签名分账）",
           ClauseStatus.LEDGER, "启用条件待排期", "9月复盘"),
    Clause("D-2", "EMA50 例外候选（ALERT带条款）", ClauseStatus.LEDGER,
           "EMA50 上方回撤=结构未坏或需补 ALERT 带条款，观察 8-12 周入 v1.3 复盘", "BJ 判例"),
)


def official_clauses():
    return [c for c in CLAUSES if c.status is ClauseStatus.OFFICIAL]


def clauses_by_status(status: ClauseStatus):
    return [c for c in CLAUSES if c.status is status]
