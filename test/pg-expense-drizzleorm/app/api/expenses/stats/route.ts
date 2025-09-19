import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { expenses } from '@/lib/schema';
import { and, gte, lte, count, sum, desc, sql } from 'drizzle-orm';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const startDate = searchParams.get('startDate');
    const endDate = searchParams.get('endDate');

    const conditions = [];

    if (startDate) {
      conditions.push(gte(expenses.date, startDate));
    }

    if (endDate) {
      conditions.push(lte(expenses.date, endDate));
    }

    const whereCondition = conditions.length > 0 ? and(...conditions) : undefined;

    // Total expenses
    const totalResult = await db.select({
      count: count(),
      total: sum(expenses.amount)
    })
    .from(expenses)
    .where(whereCondition);

    // Expenses by category
    const categoryResult = await db.select({
      category: sql<string>`COALESCE(${expenses.category}, 'Uncategorized')`,
      count: count(),
      total: sum(expenses.amount)
    })
    .from(expenses)
    .where(whereCondition)
    .groupBy(sql`COALESCE(${expenses.category}, 'Uncategorized')`)
    .orderBy(desc(sum(expenses.amount)));

    // Monthly aggregation
    const monthlyResult = await db.select({
      month: sql<Date>`DATE_TRUNC('month', ${expenses.date})`,
      count: count(),
      total: sum(expenses.amount)
    })
    .from(expenses)
    .where(whereCondition)
    .groupBy(sql`DATE_TRUNC('month', ${expenses.date})`)
    .orderBy(desc(sql`DATE_TRUNC('month', ${expenses.date})`));

    // Daily aggregation for last 30 days (or filtered range)
    const dailyResult = await db.select({
      date: expenses.date,
      count: count(),
      total: sum(expenses.amount)
    })
    .from(expenses)
    .where(whereCondition)
    .groupBy(expenses.date)
    .orderBy(desc(expenses.date))
    .limit(30);

    const stats = {
      total: {
        count: Number(totalResult[0].count),
        amount: parseFloat(totalResult[0].total || '0')
      },
      byCategory: categoryResult.map(row => ({
        category: row.category,
        count: Number(row.count),
        total: parseFloat(row.total || '0')
      })),
      byMonth: monthlyResult.map(row => ({
        month: row.month,
        count: Number(row.count),
        total: parseFloat(row.total || '0')
      })),
      daily: dailyResult.map(row => ({
        date: row.date,
        count: Number(row.count),
        total: parseFloat(row.total || '0')
      }))
    };

    return NextResponse.json(stats);
  } catch (error) {
    console.error('Error fetching expense stats:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}