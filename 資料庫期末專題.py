import datetime
from tkinter import messagebox
import customtkinter as ctk
import pyodbc

# ==========================================
# 0. 介面外觀整體風格設定
# ==========================================
ctk.set_appearance_mode("Dark")  # 採用高質感的深色模式
ctk.set_default_color_theme("blue")  # 以科技藍為主底色

# ==========================================
# 1. SQL Server 資料庫精密連線設定
# ==========================================
# 這裡已經完全修正為你 SSMS 畫面上的真實電腦名稱與中文資料庫名稱
SQL_SERVER_NAME = r"2026-05-12-Z01\SQLEXPRESS"
DB_NAME = "資料庫期末專題"


def get_db_connection():
    """建立與 SQL Server 的 Windows 驗證連線管道 (已加入憑證信任參數)"""
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"  # 確保大括號裡面長這樣
        f"SERVER={SQL_SERVER_NAME};"
        f"DATABASE={DB_NAME};"
        f"Trusted_Connection=yes;"
        f"TrustServerCertificate=yes;"  # ✨ 關鍵修正：解決 SSL 憑證鏈結不受信任的問題
    )
    return pyodbc.connect(conn_str)


# ==========================================
# 2. 前端 CustomTkinter 視窗配置
# ==========================================
class FullAccountingApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        # 視窗基本資訊設定
        self.title("綜合記帳系統")
        self.geometry("580x660")
        self.resizable(False, False)

        # 系統大標題
        self.title_label = ctk.CTkLabel(
            self, text="資產管理系統", font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(pady=15)

        # 建立分頁標籤頁面 (完美整合原本的多張 Excel 工作表樣態)
        self.tabview = ctk.CTkTabview(self, width=520, height=540)
        self.tabview.pack(pady=10, padx=20, fill="both", expand=True)

        self.tab_summary = self.tabview.add("總損益看板")
        self.tab_insert = self.tabview.add("快速記帳")

        # 載入並初始化各分頁的 UI 元件
        self.setup_summary_tab()
        self.setup_insert_tab()

        # 程式開啟時，預設先自動刷新一次最新帳目狀態
        self.refresh_summary()

    # ------------------------------------------
    # 分頁一：動態計算的「總損益與銀行餘額看板」
    # ------------------------------------------
    def setup_summary_tab(self):
        """建置總損益畫面的元件"""
        # 總資產淨值大看板框
        self.total_frame = ctk.CTkFrame(self.tab_summary, fg_color="#1e272e")
        self.total_frame.pack(pady=15, padx=20, fill="x")

        self.total_title = ctk.CTkLabel(
            self.total_frame, text="目前預估淨資產總額", font=ctk.CTkFont(size=14)
        )
        self.total_title.pack(pady=(10, 0))

        self.total_val = ctk.CTkLabel(
            self.total_frame,
            text="$ 0.00",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color="#2ecc71",
        )
        self.total_val.pack(pady=(0, 10))

        # 提示文字
        self.list_label = ctk.CTkLabel(
            self.tab_summary,
            text="各資產/銀行帳戶即時餘額：",
            font=ctk.CTkFont(size=14),
        )
        self.list_label.pack(anchor="w", padx=25, pady=(10, 5))

        # 滾動框架：當你銀行很多家時，會自動出現滾動條，不會擠爆畫面
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.tab_summary, width=440, height=220
        )
        self.scroll_frame.pack(pady=5, padx=20, fill="both", expand=True)

        # 手動更新按鈕
        self.refresh_btn = ctk.CTkButton(
            self.tab_summary, text="重新整理資產狀態", command=self.refresh_summary
        )
        self.refresh_btn.pack(pady=15)

    def refresh_summary(self):
        """核心邏輯：向 SQL Server 要資料，動態計算所有帳戶的最新餘額與總淨值"""
        # 每次刷新前，先清空畫面上舊的銀行名稱殘影
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 會計核心 SQL 指令：目前餘額 = 初始餘額 + 總收入 - 總支出
            sql_query = """
                SELECT
                    a.帳戶名稱,
                    (CAST(a.初始餘額 AS DECIMAL(18,2))
                     + ISNULL(SUM(CASE WHEN t.交易類型 = '收入' THEN CAST(t.金額 AS DECIMAL(18,2)) ELSE 0 END), 0)
                     - ISNULL(SUM(CASE WHEN t.交易類型 = '支出' THEN CAST(t.金額 AS DECIMAL(18,2)) ELSE 0 END), 0)) AS 目前餘額
                FROM 銀行帳戶表 a
                LEFT JOIN 收支流水帳表 t ON a.帳戶編號 = t.帳戶編號
                GROUP BY a.帳戶名稱, a.初始餘額;
            """
            cursor.execute(sql_query)
            rows = cursor.fetchall()

            total_net_worth = 0.0

            # 遍歷資料庫算出來的每一筆資料，動態畫到 CustomTkinter 上面
            for row in rows:
                name = row[0]
                balance = float(row[1]) if row[1] is not None else 0.0
                total_net_worth += balance

                # 每一家銀行的顯示小橫條
                item_frame = ctk.CTkFrame(
                    self.scroll_frame, fg_color="transparent"
                )
                item_frame.pack(fill="x", pady=6, padx=10)

                name_lbl = ctk.CTkLabel(
                    item_frame,
                    text=name,
                    font=ctk.CTkFont(size=14, weight="bold"),
                )
                name_lbl.pack(side="left")

                # 正數顯示水藍色，負數（例如負債或透支）顯示紅色
                bal_lbl = ctk.CTkLabel(
                    item_frame,
                    text=f"$ {balance:,.2f}",
                    font=ctk.CTkFont(size=14),
                    text_color="#3498db" if balance >= 0 else "#e74c3c",
                )
                bal_lbl.pack(side="right")

            # 更新頂部的大總資產金額
            self.total_val.configure(text=f"$ {total_net_worth:,.2f}")
            conn.close()

        except Exception as e:
            messagebox.showerror(
                "連線錯誤", f"無法成功讀取 SQL Server 數據：\n{str(e)}"
            )

    # ------------------------------------------
    # 分頁二：高質感的「快速記帳表單」
    # ------------------------------------------
    def setup_insert_tab(self):
        """建置記帳表單的元件"""
        ctk.CTkLabel(self.tab_insert, text="選擇扣款/入帳帳戶:").pack(
            anchor="w", padx=40, pady=(20, 5)
        )

        # 自動到資料庫撈取你設定的銀行名稱（例如：玉山、台新、股票現值等）
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 帳戶名稱 FROM 銀行帳戶表")
            account_options = [r[0] for r in cursor.fetchall()]
            conn.close()
            if not account_options:
                account_options = ["(資料庫中尚無帳戶資料)"]
        except:
            account_options = ["(連線失敗，請檢查資料庫設定)"]

        self.acc_dropdown = ctk.CTkOptionMenu(
            self.tab_insert, values=account_options, width=320
        )
        self.acc_dropdown.pack(pady=5)

        # 交易類型（Radio Button 橫向排列）
        ctk.CTkLabel(self.tab_insert, text="交易類型:").pack(
            anchor="w", padx=40, pady=10
        )
        self.type_var = ctk.StringVar(value="支出")
        self.radio_f = ctk.CTkFrame(self.tab_insert, fg_color="transparent")
        self.radio_f.pack()
        ctk.CTkRadioButton(
            self.radio_f, text="支出 🔻", variable=self.type_var, value="支出"
        ).pack(side="left", padx=25)
        ctk.CTkRadioButton(
            self.radio_f, text="收入 🔺", variable=self.type_var, value="收入"
        ).pack(side="left", padx=25)

        # 項目類別
        ctk.CTkLabel(self.tab_insert, text="項目類別 (對應原 Excel 項目):").pack(
            anchor="w", padx=40, pady=10
        )
        self.cat_dropdown = ctk.CTkOptionMenu(
            self.tab_insert,
            values=[
                "存款",
                "提款",
                "轉帳",
                "簽帳消費",
                "信用卡消費扣款",
                "簽帳回饋金",
                "工作薪水",
                "基金配息",
                "基金扣款",
                "利息",
                "其它",
            ],
            width=320,
        )
        self.cat_dropdown.pack(pady=5)

        # 金額輸入
        ctk.CTkLabel(self.tab_insert, text="輸入金額:").pack(
            anchor="w", padx=40, pady=10
        )
        self.amount_entry = ctk.CTkEntry(
            self.tab_insert, placeholder_text="請輸入阿拉伯數字", width=320
        )
        self.amount_entry.pack(pady=5)

        # 儲存按鈕
        self.save_btn = ctk.CTkButton(
            self.tab_insert,
            text="儲存並同步至 SQL Server",
            fg_color="#2ecc71",
            hover_color="#27ae60",
            command=self.save_to_sql,
            height=40,
        )
        self.save_btn.pack(pady=35, padx=40, fill="x")

    def save_to_sql(self):
        """觸發儲存：驗證資料後將紀錄傳遞至 SQL Server"""
        acc_name = self.acc_dropdown.get()
        tx_type = self.type_var.get()
        category = self.cat_dropdown.get()
        amount_str = self.amount_entry.get()

        # 基礎連線防呆
        if acc_name in [
            "(資料庫中尚無帳戶資料)",
            "(連線失敗，請檢查資料庫設定)",
        ]:
            messagebox.showerror(
                "儲存失敗", "無效的銀行帳戶，請先在資料庫內新增帳戶。"
            )
            return

        # 阿拉伯數字防呆驗證
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "驗證失敗", "金額欄位請輸入大於 0 的有效阿拉伯數字！"
            )
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 1. 拿前端選的「銀行名稱」去查對應的「台灣金融代碼 (varchar)」
            cursor.execute(
                "SELECT 帳戶編號 FROM 銀行帳戶表 WHERE 帳戶名稱 = ?",
                (acc_name,),
            )
            acc_id = cursor.fetchone()[0]

            # 2. 精準寫入收支流水帳表
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sql_insert = """
                INSERT INTO 收支流水帳表 (帳戶編號, 交易類型, 消費類別, 金額, 交易日期)
                VALUES (?, ?, ?, ?, ?)
            """
            cursor.execute(
                sql_insert, (acc_id, tx_type, category, amount, now_str)
            )
            conn.commit()
            conn.close()

            # 彈出成功視窗並清空輸入框
            messagebox.showinfo(
                "儲存成功",
                f"紀錄已安全同步！\n帳戶：{acc_name}\n金額：${amount:,.2f}",
            )
            self.amount_entry.delete(0, "end")

            # 自動跳回「總損益看板」分頁，讓使用者親眼看到餘額更新
            self.tabview.set("總損益看板")
            self.refresh_summary()

        except Exception as e:
            messagebox.showerror(
                "系統錯誤",
                f"無法成功寫入 SQL Server 資料表：\n{str(e)}",
            )


# ==========================================
# 3. 程式主進入點
# ==========================================
if __name__ == "__main__":
    app = FullAccountingApp()
    app.mainloop()