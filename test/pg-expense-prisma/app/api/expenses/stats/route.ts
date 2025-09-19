import { NextRequest, NextResponse } from 'next/server';
import prisma from '@/lib/db';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const startDate = searchParams.get('startDate');
    const endDate = searchParams.get('endDate');

    const where: any = {};

    if (startDate) {
      where.date = { ...where.date, gte: new Date(startDate) };
    }

    if (endDate) {
      where.date = { ...where.date, lte: new Date(endDate) };
    }

    // Total expenses
    const totalStats = await prisma.expense.aggregate({
      where,
      _count: { id: true },
      _sum: { amount: true }
    });

    // Expenses by category
    const categoryStats = await prisma.expense.groupBy({
      by: ['category'],
      where,
      _count: { id: true },
      _sum: { amount: true },
      orderBy: { _sum: { amount: 'desc' } }
    });

    // Monthly aggregation using raw SQL for DATE_TRUNC
    let monthlyQuery = `
      SELECT
        DATE_TRUNC('month', date) as month,
        COUNT(*) as count,
        SUM(amount) as total
      FROM expenses
      WHERE 1=1
    `;
    const queryParams: any[] = [];

    if (startDate) {
      queryParams.push(startDate);
      monthlyQuery += ` AND date >= $${queryParams.length}`;
    }

    if (endDate) {
      queryParams.push(endDate);
      monthlyQuery += ` AND date <= $${queryParams.length}`;
    }

    monthlyQuery += `
      GROUP BY DATE_TRUNC('month', date)
      ORDER BY month DESC
    `;

    const monthlyStats = await prisma.$queryRawUnsafe<Array<{
      month: Date;
      count: bigint;
      total: number;
    }>>(monthlyQuery, ...queryParams);

    // Daily aggregation
    const dailyStats = await prisma.expense.groupBy({
      by: ['date'],
      where,
      _count: { id: true },
      _sum: { amount: true },
      orderBy: { date: 'desc' },
      take: 30
    });

    const stats = {
      total: {
        count: totalStats._count.id,
        amount: totalStats._sum.amount ? Number(totalStats._sum.amount) : 0
      },
      byCategory: categoryStats.map(stat => ({
        category: stat.category || 'Uncategorized',
        count: stat._count.id,
        total: stat._sum.amount ? Number(stat._sum.amount) : 0
      })),
      byMonth: monthlyStats.map(stat => ({
        month: stat.month,
        count: Number(stat.count),
        total: Number(stat.total)
      })),
      daily: dailyStats.map(stat => ({
        date: stat.date,
        count: stat._count.id,
        total: stat._sum.amount ? Number(stat._sum.amount) : 0
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