"""Database storage module for stock data using SQLAlchemy.

This module provides a PostgreSQL/SQLite storage layer for persisting stock
fundamentals and price history data with efficient querying capabilities.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint,
    create_engine, func, Index
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from sqlalchemy.pool import QueuePool

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# SQLAlchemy Base
Base = declarative_base()


class Stock(Base):
    """Stock master table storing basic stock information.

    Attributes:
        id: Primary key.
        ticker: Unique stock ticker symbol (e.g., 'AAPL').
        name: Company name.
        sector: Industry sector.
        last_updated: Timestamp of last data update.
    """

    __tablename__ = 'stocks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(200))
    sector = Column(String(100))
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    fundamentals = relationship('Fundamental', back_populates='stock', cascade='all, delete-orphan')
    price_history = relationship('PriceHistory', back_populates='stock', cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return f"<Stock(ticker='{self.ticker}', name='{self.name}', sector='{self.sector}')>"


class Fundamental(Base):
    """Fundamental metrics table storing financial ratios and metrics.

    Attributes:
        id: Primary key.
        stock_id: Foreign key to Stock table.
        date: Date of fundamental data.
        pe_ratio: Price-to-Earnings ratio.
        pb_ratio: Price-to-Book ratio.
        debt_equity: Debt-to-Equity ratio.
        fcf_yield: Free Cash Flow yield.
        market_cap: Market capitalization.
        current_price: Current stock price.
        week_52_high: 52-week high price.
        week_52_low: 52-week low price.
        trailing_eps: Trailing EPS.
        forward_eps: Forward EPS.
        dividend_yield: Dividend yield percentage.
    """

    __tablename__ = 'fundamentals'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    pe_ratio = Column(Float)
    pb_ratio = Column(Float)
    debt_equity = Column(Float)
    fcf_yield = Column(Float)
    market_cap = Column(Float)
    current_price = Column(Float)
    week_52_high = Column(Float)
    week_52_low = Column(Float)
    trailing_eps = Column(Float)
    forward_eps = Column(Float)
    dividend_yield = Column(Float)

    # Relationships
    stock = relationship('Stock', back_populates='fundamentals')

    # Composite index for efficient queries
    __table_args__ = (
        Index('ix_fundamentals_stock_date', 'stock_id', 'date'),
    )

    def __repr__(self) -> str:
        return f"<Fundamental(stock_id={self.stock_id}, date='{self.date}', pe={self.pe_ratio})>"


class PriceHistory(Base):
    """Price history table storing daily OHLCV data.

    Attributes:
        id: Primary key.
        stock_id: Foreign key to Stock table.
        date: Trading date.
        open: Opening price.
        high: High price.
        low: Low price.
        close: Closing price.
        volume: Trading volume.
    """

    __tablename__ = 'price_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

    # Relationships
    stock = relationship('Stock', back_populates='price_history')

    # Composite unique constraint to prevent duplicate entries
    __table_args__ = (
        UniqueConstraint('stock_id', 'date', name='uix_stock_date'),
        Index('ix_price_history_stock_date', 'stock_id', 'date'),
    )

    def __repr__(self) -> str:
        return f"<PriceHistory(stock_id={self.stock_id}, date='{self.date}', close={self.close})>"


class DataQualityLog(Base):
    """Data quality check log table storing quality check results.

    Attributes:
        id: Primary key.
        ticker: Stock ticker symbol.
        check_date: Date when quality check was performed.
        overall_score: Overall quality score (0-100).
        has_critical_issues: Whether critical issues were found.
        needs_refresh: Whether data needs to be refreshed.
        num_issues: Total number of issues found.
        issue_summary: Summary of issues (first 5).
    """

    __tablename__ = 'data_quality_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    check_date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    overall_score = Column(Float)
    has_critical_issues = Column(Integer)  # SQLite doesn't have Boolean, use 0/1
    needs_refresh = Column(Integer)  # SQLite doesn't have Boolean, use 0/1
    num_issues = Column(Integer)
    issue_summary = Column(String(1000))

    # Composite index for efficient queries
    __table_args__ = (
        Index('ix_quality_log_ticker_date', 'ticker', 'check_date'),
    )

    def __repr__(self) -> str:
        return f"<DataQualityLog(ticker='{self.ticker}', score={self.overall_score}, date='{self.check_date}')>"


class StockDatabase:
    """Database interface for storing and querying stock data.

    This class provides methods to save and retrieve stock fundamentals and
    price history data using SQLAlchemy ORM with support for PostgreSQL and SQLite.

    Attributes:
        engine: SQLAlchemy engine instance.
        Session: SQLAlchemy session factory.

    Example:
        >>> db = StockDatabase()
        >>> db.save_stock_fundamentals("AAPL", {"pe_ratio": 25.5, "pb_ratio": 45.2})
        >>> history = db.get_price_history("AAPL", "2023-01-01", "2024-01-01")
        >>> cheap = db.query_cheap_stocks(pe_max=15, pb_max=1.5)
    """

    def __init__(self, db_url: Optional[str] = None) -> None:
        """Initialize the StockDatabase with connection to PostgreSQL or SQLite.

        Args:
            db_url: Database URL. If None, reads from DATABASE_URL environment variable.
                   Falls back to SQLite if not provided.

        Example:
            >>> db = StockDatabase("postgresql://user:pass@localhost:5432/stocks")
            >>> db = StockDatabase("sqlite:///./stock_screener.db")
            >>> db = StockDatabase()  # Uses environment variable or SQLite
        """
        if db_url is None:
            db_url = os.getenv('DATABASE_URL', 'sqlite:///./stock_screener.db')

        logger.info(f"Initializing database connection: {db_url.split('@')[-1]}")

        # Create engine with connection pooling for production
        if db_url.startswith('postgresql'):
            self.engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,  # Verify connections before using
                echo=False
            )
        else:
            self.engine = create_engine(db_url, echo=False)

        # Create session factory
        self.Session = sessionmaker(bind=self.engine)

        # Create all tables
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created/verified successfully")

    def _get_or_create_stock(self, session: Session, ticker: str, name: str = None, sector: str = None) -> Stock:
        """Get existing stock or create new one.

        Args:
            session: SQLAlchemy session.
            ticker: Stock ticker symbol.
            name: Company name (optional).
            sector: Industry sector (optional).

        Returns:
            Stock ORM object.
        """
        stock = session.query(Stock).filter_by(ticker=ticker.upper()).first()

        if stock is None:
            stock = Stock(
                ticker=ticker.upper(),
                name=name or ticker,
                sector=sector or 'Unknown'
            )
            session.add(stock)
            session.flush()  # Get the ID without committing
            logger.info(f"Created new stock entry: {ticker}")
        else:
            # Update name and sector if provided
            if name and stock.name != name:
                stock.name = name
            if sector and stock.sector != sector:
                stock.sector = sector
            stock.last_updated = datetime.utcnow()

        return stock

    def save_stock_fundamentals(self, ticker: str, data: Dict[str, any]) -> None:
        """Save fundamental data for a stock.

        Args:
            ticker: Stock ticker symbol.
            data: Dictionary containing fundamental metrics. Expected keys:
                 'name', 'sector', 'pe_ratio', 'pb_ratio', 'debt_to_equity',
                 'free_cash_flow', 'current_price', 'week_52_high', 'week_52_low',
                 'market_cap', 'trailing_eps', 'forward_eps', 'dividend_yield'.

        Raises:
            SQLAlchemyError: If database operation fails.

        Example:
            >>> db = StockDatabase()
            >>> data = {
            ...     'name': 'Apple Inc.',
            ...     'sector': 'Technology',
            ...     'pe_ratio': 25.5,
            ...     'pb_ratio': 45.2,
            ...     'debt_to_equity': 1.73
            ... }
            >>> db.save_stock_fundamentals("AAPL", data)
        """
        session = self.Session()
        try:
            # Get or create stock
            stock = self._get_or_create_stock(
                session,
                ticker,
                data.get('name'),
                data.get('sector')
            )

            # Create fundamental entry
            fundamental = Fundamental(
                stock_id=stock.id,
                date=datetime.utcnow(),
                pe_ratio=data.get('pe_ratio'),
                pb_ratio=data.get('pb_ratio'),
                debt_equity=data.get('debt_to_equity'),
                fcf_yield=self._calculate_fcf_yield(data),
                market_cap=data.get('market_cap'),
                current_price=data.get('current_price'),
                week_52_high=data.get('week_52_high'),
                week_52_low=data.get('week_52_low'),
                trailing_eps=data.get('trailing_eps'),
                forward_eps=data.get('forward_eps'),
                dividend_yield=data.get('dividend_yield')
            )

            session.add(fundamental)
            session.commit()
            logger.info(f"Saved fundamentals for {ticker}")

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to save fundamentals for {ticker}: {e}")
            raise
        finally:
            session.close()

    def _calculate_fcf_yield(self, data: Dict[str, any]) -> Optional[float]:
        """Calculate Free Cash Flow yield.

        Args:
            data: Dictionary containing 'free_cash_flow' and 'market_cap'.

        Returns:
            FCF yield as percentage, or None if calculation not possible.
        """
        fcf = data.get('free_cash_flow')
        market_cap = data.get('market_cap')

        if fcf and market_cap and market_cap > 0:
            return (fcf / market_cap) * 100
        return None

    def save_price_history(self, ticker: str, df: pd.DataFrame) -> None:
        """Save historical price data for a stock (bulk insert).

        Args:
            ticker: Stock ticker symbol.
            df: DataFrame with columns: Date, Open, High, Low, Close, Volume.

        Raises:
            ValueError: If DataFrame is empty or missing required columns.
            SQLAlchemyError: If database operation fails.

        Example:
            >>> db = StockDatabase()
            >>> prices = pd.DataFrame({
            ...     'Date': ['2024-01-01', '2024-01-02'],
            ...     'Open': [150.0, 151.0],
            ...     'High': [152.0, 153.0],
            ...     'Low': [149.0, 150.0],
            ...     'Close': [151.0, 152.0],
            ...     'Volume': [1000000, 1100000]
            ... })
            >>> db.save_price_history("AAPL", prices)
        """
        if df.empty:
            logger.warning(f"Empty DataFrame provided for {ticker}")
            return

        required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"DataFrame missing required columns: {missing_cols}")

        session = self.Session()
        try:
            # Get or create stock
            stock = self._get_or_create_stock(session, ticker)

            # Prepare bulk insert data
            records = []
            for _, row in df.iterrows():
                records.append({
                    'stock_id': stock.id,
                    'date': pd.to_datetime(row['Date']),
                    'open': float(row['Open']) if pd.notna(row['Open']) else None,
                    'high': float(row['High']) if pd.notna(row['High']) else None,
                    'low': float(row['Low']) if pd.notna(row['Low']) else None,
                    'close': float(row['Close']) if pd.notna(row['Close']) else None,
                    'volume': float(row['Volume']) if pd.notna(row['Volume']) else None
                })

            # Bulk insert with ignore on conflict (for duplicates)
            if records:
                for record in records:
                    try:
                        price = PriceHistory(**record)
                        session.add(price)
                    except IntegrityError:
                        session.rollback()
                        # Update existing record instead
                        existing = session.query(PriceHistory).filter_by(
                            stock_id=record['stock_id'],
                            date=record['date']
                        ).first()
                        if existing:
                            for key, value in record.items():
                                if key not in ['stock_id', 'date']:
                                    setattr(existing, key, value)

                session.commit()
                logger.info(f"Saved {len(records)} price records for {ticker}")

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to save price history for {ticker}: {e}")
            raise
        finally:
            session.close()

    def get_latest_fundamentals(self, ticker: str) -> Dict[str, any]:
        """Retrieve the most recent fundamental data for a stock.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            Dictionary containing fundamental metrics, or empty dict if not found.

        Example:
            >>> db = StockDatabase()
            >>> data = db.get_latest_fundamentals("AAPL")
            >>> print(data['pe_ratio'])
        """
        session = self.Session()
        try:
            stock = session.query(Stock).filter_by(ticker=ticker.upper()).first()

            if not stock:
                logger.warning(f"Stock {ticker} not found in database")
                return {}

            # Get most recent fundamental entry
            fundamental = (
                session.query(Fundamental)
                .filter_by(stock_id=stock.id)
                .order_by(Fundamental.date.desc())
                .first()
            )

            if not fundamental:
                logger.warning(f"No fundamental data found for {ticker}")
                return {}

            return {
                'ticker': stock.ticker,
                'name': stock.name,
                'sector': stock.sector,
                'date': fundamental.date.isoformat(),
                'pe_ratio': fundamental.pe_ratio,
                'pb_ratio': fundamental.pb_ratio,
                'debt_equity': fundamental.debt_equity,
                'fcf_yield': fundamental.fcf_yield,
                'market_cap': fundamental.market_cap,
                'current_price': fundamental.current_price,
                'week_52_high': fundamental.week_52_high,
                'week_52_low': fundamental.week_52_low,
                'trailing_eps': fundamental.trailing_eps,
                'forward_eps': fundamental.forward_eps,
                'dividend_yield': fundamental.dividend_yield
            }

        except SQLAlchemyError as e:
            logger.error(f"Failed to get fundamentals for {ticker}: {e}")
            return {}
        finally:
            session.close()

    def get_price_history(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """Retrieve historical price data for a stock within a date range.

        Args:
            ticker: Stock ticker symbol.
            start_date: Start date in 'YYYY-MM-DD' format.
            end_date: End date in 'YYYY-MM-DD' format.

        Returns:
            DataFrame with columns: Date, Open, High, Low, Close, Volume.
            Returns empty DataFrame if no data found.

        Example:
            >>> db = StockDatabase()
            >>> prices = db.get_price_history("AAPL", "2023-01-01", "2024-01-01")
            >>> print(prices.head())
        """
        session = self.Session()
        try:
            stock = session.query(Stock).filter_by(ticker=ticker.upper()).first()

            if not stock:
                logger.warning(f"Stock {ticker} not found in database")
                return pd.DataFrame()

            # Parse dates
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')

            # Query price history
            prices = (
                session.query(PriceHistory)
                .filter(
                    PriceHistory.stock_id == stock.id,
                    PriceHistory.date >= start,
                    PriceHistory.date <= end
                )
                .order_by(PriceHistory.date)
                .all()
            )

            if not prices:
                logger.warning(f"No price history found for {ticker} in date range")
                return pd.DataFrame()

            # Convert to DataFrame
            data = {
                'Date': [p.date for p in prices],
                'Open': [p.open for p in prices],
                'High': [p.high for p in prices],
                'Low': [p.low for p in prices],
                'Close': [p.close for p in prices],
                'Volume': [p.volume for p in prices]
            }

            df = pd.DataFrame(data)
            logger.info(f"Retrieved {len(df)} price records for {ticker}")
            return df

        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return pd.DataFrame()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get price history for {ticker}: {e}")
            return pd.DataFrame()
        finally:
            session.close()

    def query_cheap_stocks(
        self,
        pe_max: float = 15,
        pb_max: float = 1.5,
        min_market_cap: Optional[float] = None
    ) -> List[str]:
        """Query stocks that meet value investing criteria.

        Args:
            pe_max: Maximum P/E ratio threshold (default: 15).
            pb_max: Maximum P/B ratio threshold (default: 1.5).
            min_market_cap: Minimum market cap filter (optional).

        Returns:
            List of ticker symbols meeting the criteria.

        Example:
            >>> db = StockDatabase()
            >>> cheap_stocks = db.query_cheap_stocks(pe_max=15, pb_max=1.5)
            >>> print(cheap_stocks)
            ['AAPL', 'MSFT', 'GOOGL']
        """
        session = self.Session()
        try:
            # Subquery to get latest fundamental for each stock
            subq = (
                session.query(
                    Fundamental.stock_id,
                    func.max(Fundamental.date).label('max_date')
                )
                .group_by(Fundamental.stock_id)
                .subquery()
            )

            # Main query with filters
            query = (
                session.query(Stock.ticker)
                .join(Fundamental, Stock.id == Fundamental.stock_id)
                .join(subq, (Fundamental.stock_id == subq.c.stock_id) &
                           (Fundamental.date == subq.c.max_date))
                .filter(
                    Fundamental.pe_ratio.isnot(None),
                    Fundamental.pb_ratio.isnot(None),
                    Fundamental.pe_ratio > 0,
                    Fundamental.pe_ratio <= pe_max,
                    Fundamental.pb_ratio > 0,
                    Fundamental.pb_ratio <= pb_max
                )
            )

            # Add market cap filter if specified
            if min_market_cap is not None:
                query = query.filter(
                    Fundamental.market_cap.isnot(None),
                    Fundamental.market_cap >= min_market_cap
                )

            results = query.order_by(Stock.ticker).all()
            tickers = [r[0] for r in results]

            logger.info(
                f"Found {len(tickers)} stocks with PE <= {pe_max} and PB <= {pb_max}"
            )
            return tickers

        except SQLAlchemyError as e:
            logger.error(f"Failed to query cheap stocks: {e}")
            return []
        finally:
            session.close()

    def get_all_tickers(self) -> List[str]:
        """Get list of all tickers in the database.

        Returns:
            List of ticker symbols.

        Example:
            >>> db = StockDatabase()
            >>> tickers = db.get_all_tickers()
            >>> print(tickers)
        """
        session = self.Session()
        try:
            stocks = session.query(Stock.ticker).order_by(Stock.ticker).all()
            return [s[0] for s in stocks]
        except SQLAlchemyError as e:
            logger.error(f"Failed to get all tickers: {e}")
            return []
        finally:
            session.close()
