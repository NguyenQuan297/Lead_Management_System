# Đẩy code lên GitHub

Chạy các lệnh sau **trong terminal** (PowerShell hoặc CMD) tại thư mục project.

## 1. Mở terminal tại thư mục project

```powershell
cd "c:\Users\Admin\OneDrive - Troy University\Lead_Management_System"
```

## 2. Khởi tạo Git (nếu chưa có)

```powershell
git init
```

## 3. Thêm file và commit

```powershell
git add -A
git commit -m "Initial commit: Lead Management System - FPT Education"
```

## 4. Tạo repository trên GitHub

1. Vào https://github.com/new  
2. Đặt tên repo (ví dụ: `Lead_Management_System`)  
3. Chọn **Public** (hoặc Private nếu bạn muốn)  
4. **Không** chọn "Add a README" (vì đã có sẵn trong project)  
5. Bấm **Create repository**

## 5. Kết nối và đẩy code lên GitHub

Thay `YOUR_USERNAME` và `YOUR_REPO` bằng tên GitHub và tên repo của bạn:

```powershell
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

**Ví dụ:** Nếu username là `fptedu` và repo là `Lead_Management_System`:

```powershell
git remote add origin https://github.com/fptedu/Lead_Management_System.git
git push -u origin main
```

## Lưu ý

- File **.env** (mật khẩu, mã đăng ký) **không** được đẩy lên nhờ `.gitignore`.
- **lead_management.db** và **.shared_leads.json** cũng không được đẩy lên.
- Nếu GitHub yêu cầu đăng nhập, dùng **Personal Access Token** thay cho mật khẩu, hoặc đăng nhập qua trình duyệt (GitHub CLI).
