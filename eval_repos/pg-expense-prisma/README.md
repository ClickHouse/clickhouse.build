# Expense Tracker with Prisma

A full-stack expense tracking application built with Next.js, TypeScript, Tailwind CSS, PostgreSQL, and Prisma ORM. Features a modern UI with toast notifications, analytics dashboard, and support for millions of expense records.

## Features

- ✨ **Modern UI** - Clean, responsive design with Tailwind CSS
- 📊 **Analytics Dashboard** - Comprehensive expense analytics with charts and statistics
- 🔔 **Toast Notifications** - User-friendly notifications instead of browser alerts
- 💰 **Smart Form** - Quick-add buttons for common amounts ($5, $10, $15, $20)
- 🏷️ **Category Tracking** - Organize expenses by predefined categories
- ⚡ **High Performance** - Handles millions of records with optimized Prisma queries
- 🎨 **Theme Support** - Basic dark/light theme detection (body styling only)

## Tech Stack

- **Frontend**: Next.js 15, React 19, TypeScript
- **Styling**: Tailwind CSS v4
- **Database**: PostgreSQL 17
- **ORM**: Prisma 5.x with Prisma Client
- **Development**: Docker Compose for local PostgreSQL

## Prerequisites

- Node.js 18+
- Docker and Docker Compose
- Git

## Getting Started

### 1. Clone the Repository

```bash
git clone <repository-url>
cd pg-expense-example
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Set Up Environment Variables

Copy the example environment file and configure your database connection:

```bash
cp .env.example .env
```

The `.env` file should contain:

```bash
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/expense_db"
```

### 4. Set Up the Database

Start PostgreSQL using Docker Compose:

```bash
docker-compose up -d
```

This will:
- Start PostgreSQL 17 on port 5432
- Create a database named `expense_db`
- Use default credentials (postgres/postgres)
- Initialize the expenses table via `init.sql`

### 5. Generate Prisma Client and Push Schema

Generate the Prisma client and push the schema to your database:

```bash
npx prisma generate
npx prisma db push
```

### 6. Run the Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the application.

## Database Seeding

To populate the database with synthetic data for testing:

```bash
npm run seed
```

**Note**: This creates **1 million** synthetic expense records by default. You can customize this by setting the `SEED_EXPENSE_ROWS` environment variable:

```bash
SEED_EXPENSE_ROWS=100000 npm run seed  # Create 100,000 records
```

The seeding script generates realistic:
- Expense descriptions by category
- Amount ranges appropriate for each category
- Random dates over the last 2 years
- Proper category distribution

## API Endpoints

### Expenses

- `POST /api/expenses` - Create a new expense
  ```json
  {
    "description": "Lunch",
    "amount": 15.50,
    "category": "Food & Dining",
    "date": "2024-01-15"
  }
  ```

- `GET /api/expenses` - List expenses with optional filters
  - Query params: `startDate`, `endDate`, `category`

- `GET /api/expenses/stats` - Get expense analytics
  - Returns: total overview, category breakdown, monthly trends, daily activity

## Project Structure

```
├── app/
│   ├── api/expenses/          # API routes
│   ├── analytics/             # Analytics page
│   ├── page.tsx              # Home page with expense form
│   └── layout.tsx            # Root layout
├── components/
│   ├── ExpenseForm.tsx       # Expense input form
│   └── Toast.tsx            # Toast notification system
├── lib/
│   └── db.ts               # Prisma client connection
├── prisma/
│   └── schema.prisma      # Prisma database schema
├── scripts/
│   └── seed-database.js    # Database seeding script (using Prisma)
├── docker-compose.yml      # PostgreSQL setup
├── init.sql               # Database schema
├── .env                   # Environment variables
└── .env.example          # Environment variables template
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run seed` - Seed database with synthetic data using Prisma
- `npm run db:generate` - Generate Prisma client
- `npm run db:push` - Push schema changes to database
- `npm run db:migrate` - Run database migrations
- `npm run db:studio` - Open Prisma Studio (database GUI)

## Database Schema

The Prisma schema is defined in `prisma/schema.prisma`:

```prisma
model Expense {
  id          Int      @id @default(autoincrement())
  description String
  amount      Decimal  @db.Decimal(10, 2)
  category    String?  @db.VarChar(100)
  date        DateTime @default(now()) @db.Date
  createdAt   DateTime @default(now()) @map("created_at") @db.Timestamp(6)

  @@map("expenses")
}
```

This corresponds to the following PostgreSQL table:

```sql
CREATE TABLE expenses (
  id SERIAL PRIMARY KEY,
  description TEXT NOT NULL,
  amount DECIMAL(10,2) NOT NULL,
  category VARCHAR(100),
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Categories

The application supports these expense categories:

- Food & Dining
- Transportation
- Shopping
- Entertainment
- Bills & Utilities
- Healthcare
- Travel
- Education
- Other

## Development Notes

### Database Performance

- Uses Prisma Client with connection pooling
- Optimized Prisma queries and aggregations for analytics across millions of records
- Efficient batch processing with Prisma's `createMany` for data insertion
- Raw SQL queries via `$queryRaw` for complex analytics when needed

### UI/UX Features

- Form validation with immediate feedback
- Toast notifications for success/error states
- Quick-add buttons for common expense amounts
- Responsive design for mobile and desktop
- Load time indicators for analytics

## Troubleshooting

### Database Connection Issues

1. Ensure Docker is running: `docker ps`
2. Check PostgreSQL container: `docker-compose logs postgres`
3. Verify environment variables in `.env`
4. Regenerate Prisma client: `npx prisma generate`
5. Push schema changes: `npx prisma db push`

### Prisma Issues

- If you get "Prisma Client not generated" errors, run `npx prisma generate`
- For schema changes, use `npx prisma db push` in development or `npx prisma migrate dev` for migrations
- Use `npx prisma studio` to inspect your database with a GUI

### Seeding Issues

- For large datasets (1M+ records), ensure adequate disk space
- Monitor system resources during seeding
- Seeding can be interrupted and resumed (checks existing count)
- Prisma's `createMany` is used for efficient batch insertion

### Performance

- Analytics queries are optimized but may take time with very large datasets
- Consider adding database indexes for specific query patterns
- Use connection pooling limits appropriate for your system

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Run tests (if applicable)
5. Commit your changes: `git commit -m 'Add feature'`
6. Push to the branch: `git push origin feature-name`
7. Submit a pull request
