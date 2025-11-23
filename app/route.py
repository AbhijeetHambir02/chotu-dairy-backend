from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import date, timedelta
from sqlalchemy import func, desc
import calendar

from app.models import Product, Sales
from app.schemas import (
    ProductCreate, 
    ProductResponse,
    SalesCreate,
    SalesResponse,
    CreateSalesResponse
)
from app.database import get_db


router = APIRouter(tags=["Chotu Dairy APIs"])

# ----------------- Product Routes -----------------
@router.post("/products", response_model=ProductResponse)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    new_product = Product(
        product_name=product.product_name,
        price=product.price
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


@router.get("/products", response_model=list[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).all()



# ----------------- Sales Routes -----------------
@router.post("/sales", response_model=CreateSalesResponse)
def create_sale(sale: SalesCreate, db: Session = Depends(get_db)):
    # validate product_id exists
    product = db.query(Product).filter(Product.id == sale.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    new_sale = Sales(
        name=sale.name,
        product_id=sale.product_id,
        quantity=sale.quantity,
        date=sale.date,
        total_price=sale.total_price
    )
    db.add(new_sale)
    db.commit()
    db.refresh(new_sale)
    return new_sale


@router.get("/sales", response_model=list[SalesResponse])
def get_sales(date: date = Query(default=None), db: Session = Depends(get_db)):
    query = (
        db.query(Sales.id, Sales.name, Sales.date, Sales.product_id, Sales.quantity, Sales.total_price, Product.price)
        .join(Product, Sales.product_id == Product.id)
    )
    if date:
        results = query.filter(Sales.date == date).all()
    else:
        results = query.all()

    return results


# for weekly & monthly sales with date range filter
@router.get("/sales/by-date-range", response_model=list[SalesResponse])
def get_sales(start_date: date, end_date: date, db: Session = Depends(get_db)):
    query = (
        db.query(
            Sales.id,
            Sales.name,
            Sales.date,
            Sales.product_id,
            Sales.quantity,
            Sales.total_price,
            Product.price
        )
        .join(Product, Sales.product_id == Product.id)
    )

    if start_date and end_date:
        query = query.filter(Sales.date.between(start_date, end_date))

    results = query.all()
    return results


# for aggregating sales by weekday - for weekly sales chart
@router.get("/sales/graph/weekly")
def get_weekly_sales(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db)
):
    # 1️⃣ Check if start_date is Sunday and end_date is Saturday
    if start_date.isoweekday() != 7:  # Sunday = 6
        raise HTTPException(status_code=400, detail="Start date must be a Sunday")
    if end_date.isoweekday() != 6:    # Saturday = 5
        raise HTTPException(status_code=400, detail="End date must be a Saturday")
    if (end_date - start_date).days != 6:
        raise HTTPException(status_code=400, detail="Dates must form a full week (Sunday → Saturday)")

    # 2️⃣ Initialize all weekdays with 0
    weekday_totals = {day: 0 for day in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]}

    # 3️⃣ Query total sales per date in the week
    results = (
        db.query(
            Sales.date,
            func.sum(Sales.total_price).label("total")
        )
        .filter(Sales.date.between(start_date, end_date))
        .group_by(Sales.date)
        .all()
    )

    # 4️⃣ Map date totals to weekday
    for row in results:
        weekday_name = calendar.day_name[row.date.weekday()][:3]  # "Sun", "Mon", ...
        weekday_totals[weekday_name] += float(row.total)

    # 5️⃣ Convert dict to ordered list Sun → Sat
    ordered_days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    response = [{"day": day, "total": weekday_totals[day]} for day in ordered_days]

    return response



# for aggregating sales by date - for monthly sales chart

@router.get("/sales/graph/monthly")
def get_monthly_sales(
    year: int = Query(...),
    month: int = Query(...),
    db: Session = Depends(get_db)
):
    # 1️⃣ Determine number of days in the month
    num_days = calendar.monthrange(year, month)[1]

    # 2️⃣ Initialize all days with total = 0
    day_totals = {str(day): 0 for day in range(1, num_days + 1)}

    # 3️⃣ Query total sales per day
    results = (
        db.query(
            Sales.date,
            func.sum(Sales.total_price).label("total")
        )
        .filter(func.extract('year', Sales.date) == year)
        .filter(func.extract('month', Sales.date) == month)
        .group_by(Sales.date)
        .all()
    )

    # 4️⃣ Fill totals into day_totals
    for row in results:
        day_str = str(row.date.day)  # day of month as string
        day_totals[day_str] = float(row.total)

    # 5️⃣ Convert to list of dicts sorted by day
    response = [{"day": day, "total": day_totals[day]} for day in sorted(day_totals.keys(), key=int)]

    return response



# get yearly sales
@router.get("/sales/by-year", response_model=list[SalesResponse])
def get_sales_by_year(
    year: int = Query(...),
    db: Session = Depends(get_db)
):
    # Query all sales for the given year with product price
    results = (
        db.query(
            Sales.id,
            Sales.name,
            Sales.date,
            Sales.product_id,
            Sales.quantity,
            Sales.total_price,
            Product.price
        )
        .join(Product, Sales.product_id == Product.id)
        .filter(func.extract("year", Sales.date) == year)
        .order_by(Sales.date)
        .all()
    )

    return results

# yearly sales graph
@router.get("/sales/graph/yearly")
def get_yearly_sales(
    year: int = Query(...),
    db: Session = Depends(get_db)
):
    if year < 1900 or year > 2100:
        raise HTTPException(status_code=400, detail="Invalid year")

    # 1️⃣ Initialize months Jan → Dec with total = 0
    month_totals = {calendar.month_abbr[i]: 0 for i in range(1, 13)}  # "Jan", "Feb", ...

    # 2️⃣ Query sales totals grouped by month
    results = (
        db.query(
            func.extract("month", Sales.date).label("month"),
            func.sum(Sales.total_price).label("total")
        )
        .filter(func.extract("year", Sales.date) == year)
        .group_by(func.extract("month", Sales.date))
        .all()
    )

    # 3️⃣ Fill totals into month_totals
    for row in results:
        month_name = calendar.month_abbr[int(row.month)]
        month_totals[month_name] = float(row.total)

    # 4️⃣ Convert to list of dicts in order Jan → Dec
    ordered_months = list(calendar.month_abbr)[1:]  # skip empty string at index 0
    response = [{"month": month, "total": month_totals[month]} for month in ordered_months]

    return response


# give total sales for today, week, month, year
@router.get("/sales/summary")
def get_sales_summary(db: Session = Depends(get_db)):
    today = date.today()

    # --- Daily total ---
    daily_total = db.query(func.sum(Sales.total_price)) \
        .filter(Sales.date == today) \
        .scalar() or 0

    # --- Current week total (Sunday → Saturday) ---
    # Find current week Sunday
    start_of_week = today - timedelta(days=today.weekday() + 1 if today.weekday() != 6 else 0)
    end_of_week = start_of_week + timedelta(days=6)

    weekly_total = db.query(func.sum(Sales.total_price)) \
        .filter(Sales.date.between(start_of_week, end_of_week)) \
        .scalar() or 0

    # --- Current month total ---
    start_of_month = today.replace(day=1)
    last_day_of_month = calendar.monthrange(today.year, today.month)[1]
    end_of_month = today.replace(day=last_day_of_month)

    monthly_total = db.query(func.sum(Sales.total_price)) \
        .filter(Sales.date.between(start_of_month, end_of_month)) \
        .scalar() or 0

    # --- Current year total ---
    start_of_year = today.replace(month=1, day=1)
    end_of_year = today.replace(month=12, day=31)

    yearly_total = db.query(func.sum(Sales.total_price)) \
        .filter(Sales.date.between(start_of_year, end_of_year)) \
        .scalar() or 0

    return {
        "today": float(daily_total),
        "week": float(weekly_total),
        "month": float(monthly_total),
        "year": float(yearly_total)
    }



# Top 5 selling products
@router.get("/sales/top-products")
def get_top_products(db: Session = Depends(get_db), limit: int = 5):
    # Aggregate total quantity sold per product
    results = (
        db.query(
            Sales.product_id,
            Product.product_name.label("product_name"),
            func.sum(Sales.quantity).label("total_quantity"),
            func.sum(Sales.total_price).label("total_sales")
        )
        .join(Product, Sales.product_id == Product.id)
        .group_by(Sales.product_id, Product.product_name)
        .order_by(desc("total_quantity"))  # sort by quantity sold
        .limit(limit)
        .all()
    )

    # Convert results to list of dicts
    top_products = [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "total_quantity": int(r.total_quantity),
            "total_sales": float(r.total_sales)
        }
        for r in results
    ]

    return top_products


# delete product by id
@router.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    # Fetch product
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # OPTIONAL: prevent deletion if sales exist
    sales_exists = db.query(Sales).filter(Sales.product_id == product_id).first()
    if sales_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete: Product is used in sales records"
        )

    # Delete product
    db.delete(product)
    db.commit()

    return {"message": "Product deleted successfully"}