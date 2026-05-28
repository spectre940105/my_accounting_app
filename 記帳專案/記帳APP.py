import streamlit as st
import pyodbc
import pandas as pd

# ==========================================
# 1. 資料庫連線設定
# ==========================================
def get_db_connection():
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};'
        'SERVER=2026-05-12-Z01\SQLEXPRESS;'
        'DATABASE=資料庫期末專題重製版;'
        'Trusted_Connection=yes;' #使用 Windows 身分驗證
        'Encrypt=yes;'                  # 新增這一行（開啟加密）
        'TrustServerCertificate=yes;' #新增這一行（信任伺服器憑證）
    )
    return conn

# ==========================================
# 2. 初始化 Session State (身分驗證狀態管理)
# ==========================================
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None

# ==========================================
# 3. 側邊欄：會員登入與註冊系統
# ==========================================
st.sidebar.title("個人選單")

if st.session_state['user_id'] is None:
    auth_mode = st.sidebar.radio("切換功能", ["會員登入", "註冊新會員"])

# 會員登入表單
    if auth_mode == "會員登入":
        auth_username = st.sidebar.text_input("帳號 (Username)", key="auth_user")
        auth_password = st.sidebar.text_input("密碼 (Password)", type="password", key="auth_pass")
        if st.sidebar.button("登入"):
            if auth_username and auth_password:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, username FROM Users WHERE username = ? AND password_hash = ?", (auth_username, auth_password))
                user = cursor.fetchone()
                conn.close()

                if user:
                    st.session_state['user_id'] = user[0]
                    st.session_state['username'] = user[1]
                    st.sidebar.success(f"歡迎回來，{user[1]}！")
                    st.rerun()
                else:
                    st.sidebar.error("帳號或密碼錯誤！")
            else:
                st.sidebar.warning("請輸入帳號與密碼")

# 註冊新會員表單
    elif auth_mode == "註冊新會員":
        auth_username = st.sidebar.text_input("帳號 (Username)", max_chars=20, key="auth_user")
        auth_password = st.sidebar.text_input("密碼 (Password)", type="password", key="auth_pass")
        auth_email = st.sidebar.text_input("電子信箱 (Email)", key="auth_email")
        if st.sidebar.button("註冊"):
            if auth_username and auth_password:
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO Users (username, password_hash, email) VALUES (?, ?, ?)", (auth_username, auth_password, auth_email))
                    conn.commit()
                    st.sidebar.success("註冊成功！請切換至登入畫面。")
                except pyodbc.IntegrityError:
                    st.sidebar.error("此帳號已被註冊！")
                finally:
                    conn.close()
            else:
                st.sidebar.warning("帳號與密碼為必填項目")
else:
    st.sidebar.write(f"👤 當前登入：**{st.session_state['username']}**")
    if st.sidebar.button("登出系統"):
        st.session_state['user_id'] = None
        st.session_state['username'] = None
        st.rerun()

# ==========================================
# 4. 主畫面：記帳核心功能 (需登入後可見)
# ==========================================
if st.session_state['user_id'] is not None:
    current_user_id = st.session_state['user_id']
    st.title(f"📊 {st.session_state['username']} 的個人財務管理系統")

    conn = get_db_connection()

    # ------------------------------------------
    # 功能 A：日常記帳功能 (呼交 Stored Procedure)
    # ------------------------------------------
    st.subheader("📝 新增日常收支")

    # 撈取該使用者目前擁有的帳戶
    user_acc_query = f"SELECT ua.account_id, b.bank_id, b.bank_name, ua.account_name, ua.balance FROM User_Accounts ua JOIN Banks b ON ua.bank_id = b.bank_id WHERE ua.user_id = {current_user_id}"
    user_acc_df = pd.read_sql(user_acc_query, conn)

    # 撈取所有記帳分類
    categories_df = pd.read_sql("SELECT category_id, category_name, type FROM Categories", conn)
    categories_df['display'] = categories_df['category_name'] + " (" + categories_df['type'] + ")"

    if user_acc_df.empty:
        st.info("您目前尚未綁定任何銀行帳戶，請先在最下方完成綁定以開始記帳。")
    else:
        user_acc_df['display'] = user_acc_df.apply(lambda row: f"{row['bank_id']} {row['account_name']} (餘額: {int(float(row['balance']))})", axis=1)
        #使用三欄讓使用者同時選擇帳戶、收支類型與分類
        col_acc,col_type,col_cat = st.columns([3,2,3])
        with col_acc:
            chosen_acc = st.selectbox("帳戶選擇", options=user_acc_df.to_dict('records'), format_func=lambda x: x['display'])
        with col_type:
            chosen_type = st.radio("收支類型", options=["支出", "收入"],horizontal=True)
        with col_cat:
            filtered_cat_df = categories_df[categories_df['type'] == chosen_type]
            chosen_cat = st.selectbox("選擇交易分類", options=filtered_cat_df.to_dict('records'), format_func=lambda x: x['category_name'])

        tx_amount = st.number_input("交易金額", min_value=0.00 ,value=0.00, step=10.0)
        tx_desc = st.text_input("備註說明", placeholder="例如：購物、N月薪水")

        if st.button("確認送出記帳"):
            cursor = conn.cursor()
            try:
                #使用 try 嘗試呼叫預存程序
                cursor.execute(
                    "{CALL sp_InsertTransaction (?, ?, ?, ?)}",
                    (chosen_acc['account_id'], chosen_cat['category_id'], tx_amount, tx_desc)
                )
                conn.commit()
                st.success("記帳成功！資產餘額已自動計算更新。")
                st.rerun()

            except pyodbc.Error as e:
                # 如果 SQL 顯是 RAISERROR，會在這裡被 except 攔截抓住！
                # e.args[1] 裡面就包含你在 SQL 裡寫的「記帳失敗：該帳戶餘額不足...」
                err_msg = e.args[1]

                # 清理微軟驅動程式自帶的錯誤雜訊代號，只留下真實的中文字訊息
                if "NVARCHAR" in err_msg or "記帳失敗" in err_msg:
                    clean_msg = err_msg.split(']')[-1].strip() # 抓取最後面的純文字
                else:
                    clean_msg = "系統處理錯誤，請檢查輸入內容或餘額是否充足。"

                st.error(f"⚠️ {clean_msg}")
    st.markdown("---")

    # ------------------------------------------
    # 功能 C：明細與錯帳刪除 (使用 View 查詢 + 觸發 Trigger)
    # ------------------------------------------
    st.subheader("📜 歷史記帳明細與刪除")

    # 💡 直接透過 View 撈取資料，不需要在 Python 中對 bank_id 做特別轉換
    view_query = f"SELECT tx_id, bank_id, bank_name, account_name, category_name, transaction_type, amount, tx_date, description FROM v_UserTransactions WHERE user_id = {current_user_id} ORDER BY tx_date DESC"
    history_df = pd.read_sql(view_query, conn)

    if history_df.empty:
        st.write("目前尚無任何交易紀錄。")
    else:
        display_df = history_df.rename(columns={
            'tx_id': '交易序號', 'bank_id': '銀行代碼', 'bank_name': '銀行名稱',
            'account_name': '帳戶別名', 'category_name': '分類',
            'transaction_type': '收支類型', 'amount': '金額',
            'tx_date': '交易時間', 'description': '備註'
        })

        st.dataframe(display_df, use_container_width=True)

        st.subheader("⚠️ 記錯帳刪除區")
        tx_to_delete = st.selectbox("選擇欲刪除的交易序號", options=history_df['tx_id'].tolist())

        if st.button("確認刪除此筆交易"):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Transactions WHERE tx_id = ?", (tx_to_delete,))
            conn.commit()
            st.success(f"交易序號 {tx_to_delete} 已刪除！Trigger 已自動將金額校正回您的帳戶。")
            st.rerun()
    st.markdown("---")


 # ------------------------------------------
    # 功能 C：開戶/綁定銀行帳戶
    # ------------------------------------------
    st.subheader("綁定銀行帳戶")
    with st.expander("點擊展開 : 開戶功能"):
        all_banks_df = pd.read_sql("SELECT bank_id, bank_name FROM Banks", conn)
        all_banks_df['display'] = all_banks_df['bank_id'] + " - " + all_banks_df['bank_name']

        selected_bank = st.selectbox("選擇要綁定的銀行", options=all_banks_df.to_dict('records'), format_func=lambda x: x['display'])
        custom_acc_name = st.text_input("自訂帳戶別名 (例如：我的薪轉戶、生活費帳戶)", placeholder="可不填")
        init_balance = st.number_input("初始帳戶餘額", min_value=0.0, step=100.0)

        if st.button("確認綁定銀行"):
            # 這裡確保使用者有選銀行
            chosen_bank_code = selected_bank['bank_id']

            # 處理別名：如果沒填，就自動帶入銀行名稱
            final_alias = custom_acc_name.strip() if custom_acc_name.strip() else selected_bank['bank_name'].strip()

            exsiting_banks = user_acc_df['bank_id'].astype(str).values

            if str(chosen_bank_code) in exsiting_banks:
                st.error("您已經綁定過此銀行了！請選擇其他銀行或刪除原有帳戶後再試。")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    # 寫入資料庫
                    cursor.execute(
                        "INSERT INTO User_Accounts (user_id, bank_id, account_name, balance) VALUES (?, ?, ?, ?)",
                        (current_user_id, chosen_bank_code, final_alias, init_balance)
                    )
                    conn.commit()
                    st.success(f"🎉 成功綁定 {final_alias} 帳戶！")
                    st.rerun()

                finally:
                    conn.close()

    st.markdown("---")

    conn.close()

else:
    st.title("💰 歡迎使用個人銀行記帳系統")
    st.info("👈 請先透過左側邊欄進行【會員登入】或【註冊新會員】以開始使用系統。")