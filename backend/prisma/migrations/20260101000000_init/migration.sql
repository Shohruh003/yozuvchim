-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "public";

-- CreateTable
CREATE TABLE "users" (
    "id" BIGINT NOT NULL,
    "username" VARCHAR(128) NOT NULL DEFAULT '',
    "full_name" VARCHAR(256) NOT NULL DEFAULT '',
    "balance" INTEGER NOT NULL DEFAULT 0,
    "has_used_free_trial" BOOLEAN NOT NULL DEFAULT false,
    "daily_limit" INTEGER NOT NULL DEFAULT 5,
    "referral_count" INTEGER NOT NULL DEFAULT 0,
    "is_blocked" BOOLEAN NOT NULL DEFAULT false,
    "role" VARCHAR(32) NOT NULL DEFAULT 'user',
    "language_code" VARCHAR(8) NOT NULL DEFAULT 'uz',
    "total_spent" INTEGER NOT NULL DEFAULT 0,
    "referred_by_id" BIGINT,
    "referral_tier" VARCHAR(16) NOT NULL DEFAULT 'level1',
    "plan" VARCHAR(32) NOT NULL DEFAULT 'free',
    "total_documents" INTEGER NOT NULL DEFAULT 0,
    "total_orders" INTEGER NOT NULL DEFAULT 0,
    "time_saved" INTEGER NOT NULL DEFAULT 0,
    "last_active" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "academic_context" JSONB,
    "vip_expires_at" TIMESTAMPTZ(6),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "requests" (
    "id" SERIAL NOT NULL,
    "user_id" BIGINT NOT NULL,
    "doc_type" VARCHAR(32) NOT NULL,
    "title" VARCHAR(512) NOT NULL,
    "title_topic" VARCHAR(512) NOT NULL DEFAULT '',
    "language" VARCHAR(16) NOT NULL,
    "level" VARCHAR(32) NOT NULL DEFAULT 'standard',
    "length" VARCHAR(8) NOT NULL DEFAULT '1',
    "price" INTEGER NOT NULL DEFAULT 0,
    "requirements_text" TEXT,
    "custom_structure" TEXT,
    "export_format" VARCHAR(16) NOT NULL DEFAULT 'docx',
    "citation_style" VARCHAR(32) NOT NULL DEFAULT 'APA',
    "quality_score" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "meta_json" JSONB NOT NULL DEFAULT '{}',
    "is_free" BOOLEAN NOT NULL DEFAULT false,
    "is_deleted" BOOLEAN NOT NULL DEFAULT false,
    "result_text" TEXT,
    "status" VARCHAR(32) NOT NULL DEFAULT 'queued',
    "current_step" INTEGER NOT NULL DEFAULT 0,
    "total_steps" INTEGER NOT NULL DEFAULT 1,
    "error_log" TEXT,
    "result_path" VARCHAR(1024),
    "result_file_id" VARCHAR(512),
    "download_token" VARCHAR(64),
    "expires_at" TIMESTAMPTZ(6),
    "locked_by" VARCHAR(64),
    "locked_at" TIMESTAMPTZ(6),
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL,
    "rating" INTEGER,
    "feedback" TEXT,

    CONSTRAINT "requests_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "payments" (
    "id" SERIAL NOT NULL,
    "user_id" BIGINT NOT NULL,
    "invoice_id" VARCHAR(64) NOT NULL,
    "amount" INTEGER NOT NULL DEFAULT 0,
    "status" VARCHAR(16) NOT NULL DEFAULT 'pending',
    "screenshot_file_id" VARCHAR(256),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "payments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "tickets" (
    "id" SERIAL NOT NULL,
    "user_id" BIGINT NOT NULL,
    "ticket_id" VARCHAR(64) NOT NULL,
    "subject" VARCHAR(256) NOT NULL,
    "message" TEXT NOT NULL,
    "status" VARCHAR(16) NOT NULL DEFAULT 'open',
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "tickets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "catalog" (
    "id" SERIAL NOT NULL,
    "title" VARCHAR(512) NOT NULL,
    "doc_type" VARCHAR(32) NOT NULL,
    "language" VARCHAR(16) NOT NULL,
    "file_path" VARCHAR(1024) NOT NULL,
    "price" INTEGER NOT NULL DEFAULT 5000,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "catalog_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "promo_codes" (
    "id" SERIAL NOT NULL,
    "code" VARCHAR(32) NOT NULL,
    "amount" INTEGER NOT NULL,
    "uses_left" INTEGER NOT NULL DEFAULT 1,
    "expires_at" TIMESTAMPTZ(6),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "promo_codes_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app_settings" (
    "key" VARCHAR(64) NOT NULL,
    "value" VARCHAR(256) NOT NULL DEFAULT '',

    CONSTRAINT "app_settings_pkey" PRIMARY KEY ("key")
);

-- CreateTable
CREATE TABLE "payment_admin_messages" (
    "id" SERIAL NOT NULL,
    "payment_id" INTEGER NOT NULL,
    "invoice_id" VARCHAR(64) NOT NULL,
    "admin_id" BIGINT NOT NULL,
    "message_id" INTEGER NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "payment_admin_messages_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "payment_cards" (
    "id" SERIAL NOT NULL,
    "number" VARCHAR(32) NOT NULL,
    "holder" VARCHAR(128) NOT NULL,
    "bank" VARCHAR(64) NOT NULL DEFAULT '',
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "sort_order" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "payment_cards_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sessions" (
    "id" TEXT NOT NULL,
    "user_id" BIGINT NOT NULL,
    "refresh_hash" VARCHAR(128) NOT NULL,
    "user_agent" VARCHAR(256),
    "ip" VARCHAR(64),
    "expires_at" TIMESTAMPTZ(6) NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_used_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "sessions_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "users_username_idx" ON "users"("username");

-- CreateIndex
CREATE INDEX "users_balance_idx" ON "users"("balance");

-- CreateIndex
CREATE INDEX "users_is_blocked_idx" ON "users"("is_blocked");

-- CreateIndex
CREATE UNIQUE INDEX "requests_download_token_key" ON "requests"("download_token");

-- CreateIndex
CREATE INDEX "requests_doc_type_idx" ON "requests"("doc_type");

-- CreateIndex
CREATE INDEX "requests_language_idx" ON "requests"("language");

-- CreateIndex
CREATE INDEX "requests_level_idx" ON "requests"("level");

-- CreateIndex
CREATE INDEX "requests_status_idx" ON "requests"("status");

-- CreateIndex
CREATE INDEX "requests_user_id_status_idx" ON "requests"("user_id", "status");

-- CreateIndex
CREATE UNIQUE INDEX "payments_invoice_id_key" ON "payments"("invoice_id");

-- CreateIndex
CREATE UNIQUE INDEX "tickets_ticket_id_key" ON "tickets"("ticket_id");

-- CreateIndex
CREATE INDEX "tickets_status_idx" ON "tickets"("status");

-- CreateIndex
CREATE INDEX "catalog_doc_type_idx" ON "catalog"("doc_type");

-- CreateIndex
CREATE INDEX "catalog_language_idx" ON "catalog"("language");

-- CreateIndex
CREATE UNIQUE INDEX "promo_codes_code_key" ON "promo_codes"("code");

-- CreateIndex
CREATE INDEX "payment_admin_messages_payment_id_idx" ON "payment_admin_messages"("payment_id");

-- CreateIndex
CREATE INDEX "payment_admin_messages_invoice_id_idx" ON "payment_admin_messages"("invoice_id");

-- CreateIndex
CREATE INDEX "payment_cards_is_active_sort_order_idx" ON "payment_cards"("is_active", "sort_order");

-- CreateIndex
CREATE UNIQUE INDEX "sessions_refresh_hash_key" ON "sessions"("refresh_hash");

-- CreateIndex
CREATE INDEX "sessions_user_id_idx" ON "sessions"("user_id");

-- CreateIndex
CREATE INDEX "sessions_expires_at_idx" ON "sessions"("expires_at");

-- AddForeignKey
ALTER TABLE "requests" ADD CONSTRAINT "requests_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "payments" ADD CONSTRAINT "payments_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "tickets" ADD CONSTRAINT "tickets_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

