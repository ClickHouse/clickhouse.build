CREATE TABLE "expenses" (
	"id" serial PRIMARY KEY NOT NULL,
	"description" text NOT NULL,
	"amount" numeric(10, 2) NOT NULL,
	"category" varchar(100),
	"date" date DEFAULT now() NOT NULL,
	"created_at" timestamp DEFAULT now()
);
