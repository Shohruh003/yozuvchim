-- AlterTable
ALTER TABLE "users" ADD COLUMN "admin_username" VARCHAR(64);
ALTER TABLE "users" ADD COLUMN "admin_password_hash" VARCHAR(256);

-- CreateIndex (unique)
CREATE UNIQUE INDEX "users_admin_username_key" ON "users"("admin_username");
