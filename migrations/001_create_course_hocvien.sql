-- ============================================================
-- Votive VA — course_hocvien table
-- Quản lý học viên khóa học Chiêm tinh Vedic
-- ============================================================

CREATE TABLE IF NOT EXISTS public.course_hocvien (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- ── Thông tin cá nhân ───────────────────────────────
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    zalo TEXT,

    -- ── Thông tin sinh (cần cho thực hành chiêm tinh) ──
    birth_date DATE,
    birth_time TIME,
    birth_location TEXT,

    -- ── Khóa học ────────────────────────────────────────
    course_name TEXT NOT NULL,          -- vd: "Chiêm tinh Vedic Cơ bản", "Nâng cao"
    batch TEXT,                         -- vd: "K1-2026", "K2-2026"
    enrollment_date DATE DEFAULT CURRENT_DATE,

    -- ── Thanh toán ──────────────────────────────────────
    payment_status TEXT DEFAULT 'pending',  -- pending / paid / refunded / partial
    payment_amount NUMERIC(12, 2),
    payment_method TEXT,                    -- sepay / vnpay / transfer / momo
    payment_code TEXT,                      -- mã giao dịch
    paid_at TIMESTAMPTZ,

    -- ── Trạng thái học viên ────────────────────────────
    status TEXT DEFAULT 'pending',          -- pending / active / graduated / dropped
    notes TEXT,                             -- ghi chú nội bộ

    -- ── Source tracking ────────────────────────────────
    source TEXT DEFAULT 'chatbot',          -- chatbot / landing / manual / referral
    referred_by TEXT                        -- nếu có người giới thiệu
);

-- ── Indexes ────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_course_hocvien_email ON public.course_hocvien(email);
CREATE INDEX IF NOT EXISTS idx_course_hocvien_phone ON public.course_hocvien(phone);
CREATE INDEX IF NOT EXISTS idx_course_hocvien_course ON public.course_hocvien(course_name);
CREATE INDEX IF NOT EXISTS idx_course_hocvien_status ON public.course_hocvien(status);
CREATE INDEX IF NOT EXISTS idx_course_hocvien_payment ON public.course_hocvien(payment_status);
CREATE INDEX IF NOT EXISTS idx_course_hocvien_created ON public.course_hocvien(created_at);

-- ── RLS: Bot chỉ đọc, không cần write policy (bot dùng service_role key) ──
ALTER TABLE public.course_hocvien ENABLE ROW LEVEL SECURITY;

-- Policy cho service_role (bot/admin) — full access
CREATE POLICY "service_role_full_access" ON public.course_hocvien
    USING (true)
    WITH CHECK (true);

-- Policy cho anon — chỉ đọc (nếu cần frontend hiển thị)
-- CREATE POLICY "anon_read_own" ON public.course_hocvien
--     FOR SELECT USING (auth.email() = email);

-- ── Trigger auto-update updated_at ─────────────────────
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_course_hocvien_updated_at
    BEFORE UPDATE ON public.course_hocvien
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at();
