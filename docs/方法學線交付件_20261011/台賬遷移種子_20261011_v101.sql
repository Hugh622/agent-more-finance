-- =====================================================================
-- 台賬遷移種子_20261011.sql — 紙面執行台賬 reason code 打標落庫種子（方法學線 P1②）
-- 唯一基準：首席《reason_code_registry_v1_20261011.html》＋ 台賬reasoncode遷移映射_v1_20261011.csv
-- 原則：只打標不重寫——原台賬文本不動，本種子為映射表落庫投影
-- 載入前提：decision 表已執行 MySQL九表_reasoncode對齊delta_20261011.sql（八類枚舉＋六字段）
-- 範圍：13 條歷史令（P0）＋首席錨例判例 4 條（P1）；15 條未決倉屬 paper_order/position_lot 域，
--       其 reason code 由映射 CSV 供給，隨 v1.1 台賬主檔遷倉時由全棧引用（不在本種子）
-- 方言：中立 SQL（兩端通用）；執行者：全棧（單寫者）；單次執行（decision_id=MIG-* 幂等錨）
-- owner 字典譯碼（v1.0.1，DDL CHECK 約束）：首席→chief｜用戶→user（CSV 保留中文標籤，落庫一律英碼）
-- 口徑附注A（交首席周檢復核）：常規規則執行令（P-008/P-009/P-012 等）八類均為異常/裁量歸因類，
--   不硬塞碼——reason_code 置空＋rule_ref 承載；如首席裁定須全量編碼，按 supersedes 鏈升版
-- =====================================================================

INSERT INTO decision
(decision_id, signal_id, chief_verdict, reason_code, reason_code_sub, rationale, evidence, owner, as_of_time, as_of_tz, snapshot_id, rule_ref, notes)
VALUES
('MIG-P-001', NULL, 'approve', 'HUMAN_OVERRIDE', NULL, '裁量性風險處置令：立項→裁決→紙面減半', '課題B證偽鏈3/3兌現；9/19紙面減~50%', 'chief', '2026-09-19 00:00:00', 'UTC（HKT 08:00，原冊僅日期）', NULL, NULL, 'MIGRATION=台賬遷移打標；chief_verdict僅表原令已簽發非新增裁定'),
('MIG-P-002', NULL, 'approve', 'RULE_VIOLATION', NULL, 'R1/R2雙觸發減磅：規則強制非裁量', '10/2收159.0＋量1.27×；減磅帶159.8-160.7/165.5-166.2', 'chief', '2026-10-05 00:00:00', 'UTC（HKT 08:00，原冊僅日期）', NULL, 'R1+R2', 'MIGRATION；依首席ZETA錨例口徑'),
('MIG-P-003', NULL, 'approve', 'HUMAN_OVERRIDE', NULL, '預承諾型時間止損令', '11月中壓至≤4%＋12/9解禁前清零評估；12/9=Day180全額日', 'chief', '2026-10-08 00:00:00', 'UTC（HKT 08:00，原冊僅日期）', NULL, NULL, 'MIGRATION；掛起中'),
('MIG-P-004', NULL, 'approve', 'RULE_VIOLATION', NULL, '二守破位強制清倉：規則強制非裁量；紀律滿分、結果偏差不修規則（在案終判）', '二守破29.7（9/24收29.57＋9/25收29.45）→9/28開28.64紙面清倉', 'chief', '2026-09-28 00:00:00', 'UTC（HKT 08:00，原冊僅日期）', NULL, 'C23', 'MIGRATION；首席錨例原文直錄；復盤終判見主報告§5'),
('MIG-P-005', NULL, 'approve', 'DATA_CONFLICT', 'LESSON_LEARNED', '口徑漂移收口＋靜態凍結新規（GLDM 85.09→85.29 定案）', '9/28起禁買；解禁=收復85.29＋50MA走平/回升雙確認（10/9終裁）；現價81.72距-4.2%', 'chief', '2026-09-28 00:00:00', 'UTC（HKT 08:00，原冊僅日期）', NULL, 'D1', 'MIGRATION；首席錨例原文直錄'),
('MIG-P-006', NULL, 'approve', 'RULE_VIOLATION', 'LESSON_LEARNED', '假突破降級→收復再確認流程執行；洗盤摩擦教訓催生C24白名單', '9/29收61.49假突破降級→9/30收復→10/2首收65.65（當日高70.29）；摩擦~7pp', 'chief', '2026-09-28 00:00:00', 'UTC（HKT 08:00，原冊僅日期）', NULL, 'C24', 'MIGRATION；輔碼=處置產出（C24規則資產）'),
('MIG-P-007', NULL, 'approve', 'REGIME_CHANGE', NULL, '市場狀態驅動凍結令', '港新倉≤6%→≤5%凍結；解凍四條件現≈2/4；HSTECH警報解除≠解凍', 'chief', '2026-09-26 00:00:00', 'UTC（HKT 08:00，原冊僅日期）', NULL, NULL, 'MIGRATION；下窗口=10/13攻MA20 24545'),
('MIG-P-008', NULL, 'approve', NULL, NULL, '規則驅動常規執行（通道B首筆）——八類為異常/裁量歸因類，碼置空由rule_ref承載（口徑附注A）', '收525.18＋量1.25×確認→10/7低524.69觸及、10/8低518.79深入', 'chief', '2026-10-05 00:00:00', 'UTC（HKT 08:00，原冊僅日期）', NULL, 'R系通道B', 'MIGRATION'),
('MIG-P-009', NULL, 'approve', NULL, NULL, 'D1框架內規則化試倉（口徑附注A）', '放量收108紙面試倉；量1.63×創52周新高；雙向：放量加/縮量破104撤', 'chief', '2026-10-07 00:00:00', 'UTC（HKT 08:00，原冊僅日期）', NULL, 'D1', 'MIGRATION'),
('MIG-P-010', NULL, 'approve', 'HUMAN_OVERRIDE', NULL, '劇本级裁量修訂：舊條款作廢→新劇本', '舊87k條款作廢→新劇本82.9-83.5k接位1%（生死線78.6k）；10/9現價82.45k', 'chief', '2026-10-08 00:00:00', 'UTC（HKT 08:00，原冊僅日期）', NULL, NULL, 'MIGRATION；掛起中'),
('MIG-P-011', NULL, 'approve', 'RULE_VIOLATION', NULL, '紅C閘線觸發強制清倉：規則強制非裁量', '收1609.46<閘線1659（-3.0%）＝紅C第1條觸發（1/3）；M-20武裝→已觸發', 'chief', '2026-10-09 00:00:00', 'UTC（HKT 08:00，原冊僅日期）', NULL, 'M-20', 'MIGRATION；10/29財報前禁加倉'),
('MIG-P-012', NULL, 'approve', NULL, NULL, '凍結令轄下常規限價掛單（口徑附注A）', '首注限價單紙面掛出；港股凍結令轄下', 'chief', '2026-10-08 00:00:00', 'UTC（HKT 08:00，原冊僅日期）', NULL, NULL, 'MIGRATION；掛起中'),
('MIG-P-013', NULL, 'approve', 'HUMAN_OVERRIDE', 'EXECUTION_SLIP', '用戶側裁定＋執行踏空並案（首席錨例）；v1.0凍結冊P-013=藥明系回踩限價', 'G2區限價（2269 53.0-53.8/2359 203-208）；2359已轉止損貼線監控196距+1.3%', 'chief', '2026-10-08 00:00:00', 'UTC（HKT 08:00，原冊僅日期）', NULL, 'G2', 'MIGRATION；首席示例P-013=SPCX雙段限價（v1.1冊口徑）冊版本歧義交周檢對齊；override_object=限價單部分撤銷，override_validity=one_shot'),
('MIG-PREC-1', NULL, 'approve', 'DATA_CONFLICT', 'LESSON_LEARNED', '多源區帶標註衝突仲裁收口；代碼校驗條款素材（黃金題#01）', 'XOM/CVX區帶誤標判例；首席錨例原文直錄', 'chief', '2026-10-11 00:00:00', 'UTC（HKT 08:00）', NULL, NULL, 'MIGRATION=判例庫P1優先級'),
('MIG-PREC-2', NULL, 'approve', 'REGIME_CHANGE', NULL, '信號刻度跨閾聯動；跨閾窄幅擺動不翻轉條款在案', '十信號3.5→4.5 ALERT判例（C17刻度聯動）', 'chief', '2026-10-11 00:00:00', 'UTC（HKT 08:00）', NULL, 'C17', 'MIGRATION=判例庫P1優先級'),
('MIG-PREC-3', NULL, 'approve', 'RULE_VIOLATION', 'LESSON_LEARNED', '工程側安全收口＋掃描器v1.1', 'finnhub key事件三波處置判例', 'chief', '2026-10-11 00:00:00', 'UTC（HKT 08:00）', NULL, NULL, 'MIGRATION=判例庫P1優先級'),
('MIG-PREC-4', NULL, 'approve', 'HUMAN_OVERRIDE', 'EXECUTION_SLIP', '用戶側裁定＋執行踏空並案', 'SPCX雙段限價部分撤銷；override：object=雙段限價單→部分撤銷，validity=one_shot', 'user', '2026-10-11 00:00:00', 'UTC（HKT 08:00）', NULL, NULL, 'MIGRATION=首席錨例；冊版本歧義見MIG-P-013');
