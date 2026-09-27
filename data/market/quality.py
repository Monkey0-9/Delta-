"""Data Quality Checker - Ensure Data Integrity

Validates market data for quality issues, missing values, outliers,
and consistency before use in research and trading.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from scipy import stats


class QualityIssue(Enum):
    """Types of data quality issues"""
    MISSING_VALUES = "missing_values"
    ZERO_VOLUME = "zero_volume"
    NEGATIVE_PRICE = "negative_price"
    EXTREME_OUTLIER = "extreme_outlier"
    PRICE_GAP = "price_gap"
    STALE_DATA = "stale_data"
    DUPLICATE_TIMESTAMPS = "duplicate_timestamps"
    INCONSISTENT_OHLC = "inconsistent_ohlc"
    SUSPICIOUS_VOLUME = "suspicious_volume"
    CROSS_EXCHANGE_MISMATCH = "cross_exchange_mismatch"


class QualitySeverity(Enum):
    """Severity levels for quality issues"""
    CRITICAL = "critical"  # Data cannot be used
    HIGH = "high"  # Data should be used with caution
    MEDIUM = "medium"  # Data may be acceptable
    LOW = "low"  # Minor issue, data likely usable


@dataclass(frozen=True, slots=True)
class QualityCheck:
    """Result of a single quality check"""
    issue_type: QualityIssue
    severity: QualitySeverity
    description: str
    affected_rows: int
    total_rows: int
    details: Optional[Dict[str, Any]] = None


@dataclass(frozen=True, slots=True)
class QualityReport:
    """Complete quality report for a dataset"""
    symbol: str
    start_date: datetime
    end_date: datetime
    total_records: int
    passed_records: int
    failed_records: int
    pass_rate: float
    checks: List[QualityCheck]
    overall_quality: str  # "EXCELLENT", "GOOD", "ACCEPTABLE", "POOR", "UNUSABLE"
    recommendations: List[str]


class DataQualityChecker:
    """Comprehensive data quality checker for market data"""
    
    def __init__(
        self,
        price_change_threshold: float = 0.20,  # 20% price change considered extreme
        volume_change_threshold: float = 5.0,  # 5x volume change considered suspicious
        stale_data_threshold_hours: int = 24,  # Data older than 24 hours is stale
        z_score_threshold: float = 3.0,  # 3 standard deviations for outlier detection
    ):
        self.price_change_threshold = price_change_threshold
        self.volume_change_threshold = volume_change_threshold
        self.stale_data_threshold = timedelta(hours=stale_data_threshold_hours)
        self.z_score_threshold = z_score_threshold
    
    def check_dataframe(
        self,
        df: pd.DataFrame,
        symbol: str,
        required_columns: List[str] = None,
    ) -> QualityReport:
        """Run comprehensive quality checks on a DataFrame"""
        if required_columns is None:
            required_columns = ['open', 'high', 'low', 'close', 'volume']
        
        checks = []
        total_records = len(df)
        
        # Check for required columns
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            checks.append(QualityCheck(
                issue_type=QualityIssue.MISSING_VALUES,
                severity=QualitySeverity.CRITICAL,
                description=f"Missing required columns: {missing_cols}",
                affected_rows=total_records,
                total_rows=total_records,
                details={'missing_columns': missing_cols},
            ))
            return self._generate_report(symbol, df, checks)
        
        # Check for missing values
        missing_check = self._check_missing_values(df)
        if missing_check:
            checks.append(missing_check)
        
        # Check for negative prices
        negative_price_check = self._check_negative_prices(df)
        if negative_price_check:
            checks.append(negative_price_check)
        
        # Check for zero volume
        zero_volume_check = self._check_zero_volume(df)
        if zero_volume_check:
            checks.append(zero_volume_check)
        
        # Check OHLC consistency
        ohlc_check = self._check_ohlc_consistency(df)
        if ohlc_check:
            checks.append(ohlc_check)
        
        # Check for price gaps
        price_gap_check = self._check_price_gaps(df)
        if price_gap_check:
            checks.append(price_gap_check)
        
        # Check for extreme outliers
        outlier_check = self._check_extreme_outliers(df)
        if outlier_check:
            checks.append(outlier_check)
        
        # Check for suspicious volume
        volume_check = self._check_suspicious_volume(df)
        if volume_check:
            checks.append(volume_check)
        
        # Check for duplicate timestamps
        duplicate_check = self._check_duplicate_timestamps(df)
        if duplicate_check:
            checks.append(duplicate_check)
        
        # Check for stale data
        stale_check = self._check_stale_data(df)
        if stale_check:
            checks.append(stale_check)
        
        return self._generate_report(symbol, df, checks)
    
    def _check_missing_values(self, df: pd.DataFrame) -> Optional[QualityCheck]:
        """Check for missing values in the dataset"""
        missing_counts = df.isnull().sum()
        total_missing = missing_counts.sum()
        
        if total_missing == 0:
            return None
        
        affected_rows = df.isnull().any(axis=1).sum()
        severity = QualitySeverity.HIGH if affected_rows / len(df) > 0.1 else QualitySeverity.MEDIUM
        
        return QualityCheck(
            issue_type=QualityIssue.MISSING_VALUES,
            severity=severity,
            description=f"Found {total_missing} missing values across {missing_counts[missing_counts > 0].shape[0]} columns",
            affected_rows=affected_rows,
            total_rows=len(df),
            details={'missing_by_column': missing_counts[missing_counts > 0].to_dict()},
        )
    
    def _check_negative_prices(self, df: pd.DataFrame) -> Optional[QualityCheck]:
        """Check for negative price values"""
        price_cols = ['open', 'high', 'low', 'close']
        negative_mask = (df[price_cols] < 0).any(axis=1)
        affected_rows = negative_mask.sum()
        
        if affected_rows == 0:
            return None
        
        return QualityCheck(
            issue_type=QualityIssue.NEGATIVE_PRICE,
            severity=QualitySeverity.CRITICAL,
            description=f"Found {affected_rows} rows with negative prices",
            affected_rows=affected_rows,
            total_rows=len(df),
            details={'negative_rows': df[negative_mask].index.tolist()},
        )
    
    def _check_zero_volume(self, df: pd.DataFrame) -> Optional[QualityCheck]:
        """Check for zero volume which may indicate data issues"""
        if 'volume' not in df.columns:
            return None
        
        zero_volume_mask = df['volume'] == 0
        affected_rows = zero_volume_mask.sum()
        
        if affected_rows == 0:
            return None
        
        severity = QualitySeverity.MEDIUM if affected_rows / len(df) < 0.05 else QualitySeverity.HIGH
        
        return QualityCheck(
            issue_type=QualityIssue.ZERO_VOLUME,
            severity=severity,
            description=f"Found {affected_rows} rows with zero volume",
            affected_rows=affected_rows,
            total_rows=len(df),
            details={'zero_volume_rows': df[zero_volume_mask].index.tolist()},
        )
    
    def _check_ohlc_consistency(self, df: pd.DataFrame) -> Optional[QualityCheck]:
        """Check if OHLC data is logically consistent"""
        required_cols = ['open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required_cols):
            return None
        
        # Check that high >= max(open, close) and low <= min(open, close)
        inconsistent_high = df['high'] < df[['open', 'close']].max(axis=1)
        inconsistent_low = df['low'] > df[['open', 'close']].min(axis=1)
        inconsistent_mask = inconsistent_high | inconsistent_low
        affected_rows = inconsistent_mask.sum()
        
        if affected_rows == 0:
            return None
        
        return QualityCheck(
            issue_type=QualityIssue.INCONSISTENT_OHLC,
            severity=QualitySeverity.HIGH,
            description=f"Found {affected_rows} rows with inconsistent OHLC data",
            affected_rows=affected_rows,
            total_rows=len(df),
            details={'inconsistent_rows': df[inconsistent_mask].index.tolist()},
        )
    
    def _check_price_gaps(self, df: pd.DataFrame) -> Optional[QualityCheck]:
        """Check for extreme price gaps between consecutive periods"""
        if 'close' not in df.columns:
            return None
        
        # Calculate percentage changes
        price_changes = df['close'].pct_change().abs()
        extreme_gaps = price_changes > self.price_change_threshold
        affected_rows = extreme_gaps.sum()
        
        if affected_rows == 0:
            return None
        
        severity = QualitySeverity.HIGH if affected_rows > 1 else QualitySeverity.MEDIUM
        
        return QualityCheck(
            issue_type=QualityIssue.PRICE_GAP,
            severity=severity,
            description=f"Found {affected_rows} extreme price gaps > {self.price_change_threshold*100:.1f}%",
            affected_rows=affected_rows,
            total_rows=len(df),
            details={
                'gap_dates': df[extreme_gaps].index.tolist(),
                'gap_sizes': price_changes[extreme_gaps].tolist(),
            },
        )
    
    def _check_extreme_outliers(self, df: pd.DataFrame) -> Optional[QualityCheck]:
        """Check for statistical outliers using z-scores"""
        if 'close' not in df.columns:
            return None
        
        # Calculate z-scores for closing prices
        z_scores = np.abs(stats.zscore(df['close'].dropna()))
        extreme_outliers = z_scores > self.z_score_threshold
        affected_rows = extreme_outliers.sum()
        
        if affected_rows == 0:
            return None
        
        severity = QualitySeverity.MEDIUM if affected_rows / len(df) < 0.05 else QualitySeverity.HIGH
        
        return QualityCheck(
            issue_type=QualityIssue.EXTREME_OUTLIER,
            severity=severity,
            description=f"Found {affected_rows} statistical outliers (z-score > {self.z_score_threshold})",
            affected_rows=affected_rows,
            total_rows=len(df),
            details={'outlier_dates': df.index[extreme_outliers].tolist()},
        )
    
    def _check_suspicious_volume(self, df: pd.DataFrame) -> Optional[QualityCheck]:
        """Check for suspicious volume spikes"""
        if 'volume' not in df.columns:
            return None
        
        # Calculate volume changes
        volume_changes = df['volume'].pct_change().abs()
        suspicious_volume = volume_changes > self.volume_change_threshold
        affected_rows = suspicious_volume.sum()
        
        if affected_rows == 0:
            return None
        
        severity = QualitySeverity.MEDIUM
        
        return QualityCheck(
            issue_type=QualityIssue.SUSPICIOUS_VOLUME,
            severity=severity,
            description=f"Found {affected_rows} suspicious volume spikes > {self.volume_change_threshold}x",
            affected_rows=affected_rows,
            total_rows=len(df),
            details={'suspicious_dates': df[suspicious_volume].index.tolist()},
        )
    
    def _check_duplicate_timestamps(self, df: pd.DataFrame) -> Optional[QualityCheck]:
        """Check for duplicate timestamps"""
        if df.index.name != 'timestamp' and 'timestamp' not in df.columns:
            return None
        
        timestamp_col = df.index.name if df.index.name == 'timestamp' else 'timestamp'
        duplicates = df.duplicated(subset=[timestamp_col], keep=False)
        affected_rows = duplicates.sum()
        
        if affected_rows == 0:
            return None
        
        return QualityCheck(
            issue_type=QualityIssue.DUPLICATE_TIMESTAMPS,
            severity=QualitySeverity.HIGH,
            description=f"Found {affected_rows} duplicate timestamps",
            affected_rows=affected_rows,
            total_rows=len(df),
            details={'duplicate_timestamps': df[duplicates].index.tolist()},
        )
    
    def _check_stale_data(self, df: pd.DataFrame) -> Optional[QualityCheck]:
        """Check if data is stale (old)"""
        if not hasattr(df.index, 'max'):
            return None
        
        latest_date = df.index.max()
        current_date = datetime.now()
        
        if isinstance(latest_date, str):
            latest_date = pd.to_datetime(latest_date)
        
        time_diff = current_date - latest_date
        
        if time_diff > self.stale_data_threshold:
            severity = QualitySeverity.CRITICAL if time_diff > timedelta(days=7) else QualitySeverity.HIGH
            
            return QualityCheck(
                issue_type=QualityIssue.STALE_DATA,
                severity=severity,
                description=f"Data is stale - last update was {time_diff.days} days ago",
                affected_rows=len(df),
                total_rows=len(df),
                details={
                    'latest_date': latest_date.isoformat(),
                    'current_date': current_date.isoformat(),
                    'stale_duration_days': time_diff.days,
                },
            )
        
        return None
    
    def _generate_report(
        self,
        symbol: str,
        df: pd.DataFrame,
        checks: List[QualityCheck],
    ) -> QualityReport:
        """Generate the final quality report"""
        total_records = len(df)
        
        # Count failed records
        failed_records = 0
        for check in checks:
            if check.severity in [QualitySeverity.CRITICAL, QualitySeverity.HIGH]:
                failed_records += check.affected_records
        
        passed_records = total_records - failed_records
        pass_rate = passed_records / total_records if total_records > 0 else 0.0
        
        # Determine overall quality
        critical_issues = [c for c in checks if c.severity == QualitySeverity.CRITICAL]
        high_issues = [c for c in checks if c.severity == QualitySeverity.HIGH]
        
        if critical_issues:
            overall_quality = "UNUSABLE"
        elif len(high_issues) > 3 or pass_rate < 0.8:
            overall_quality = "POOR"
        elif len(high_issues) > 1 or pass_rate < 0.9:
            overall_quality = "ACCEPTABLE"
        elif len(checks) > 0:
            overall_quality = "GOOD"
        else:
            overall_quality = "EXCELLENT"
        
        # Generate recommendations
        recommendations = self._generate_recommendations(checks, overall_quality)
        
        # Get date range
        if hasattr(df.index, 'min') and hasattr(df.index, 'max'):
            start_date = df.index.min()
            end_date = df.index.max()
        else:
            start_date = datetime.now()
            end_date = datetime.now()
        
        return QualityReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            total_records=total_records,
            passed_records=passed_records,
            failed_records=failed_records,
            pass_rate=pass_rate,
            checks=checks,
            overall_quality=overall_quality,
            recommendations=recommendations,
        )
    
    def _generate_recommendations(
        self,
        checks: List[QualityCheck],
        overall_quality: str,
    ) -> List[str]:
        """Generate recommendations based on quality issues"""
        recommendations = []
        
        for check in checks:
            if check.issue_type == QualityIssue.MISSING_VALUES:
                recommendations.append("Consider forward-fill or interpolation for missing values")
            elif check.issue_type == QualityIssue.NEGATIVE_PRICE:
                recommendations.append("Investigate source of negative prices - may indicate data error")
            elif check.issue_type == QualityIssue.ZERO_VOLUME:
                recommendations.append("Zero volume may indicate non-trading days or data issues")
            elif check.issue_type == QualityIssue.INCONSISTENT_OHLC:
                recommendations.append("OHLC inconsistency suggests data corruption - verify with alternative source")
            elif check.issue_type == QualityIssue.PRICE_GAP:
                recommendations.append("Extreme price gaps may indicate splits, dividends, or data errors")
            elif check.issue_type == QualityIssue.EXTREME_OUTLIER:
                recommendations.append("Statistical outliers should be investigated for data quality")
            elif check.issue_type == QualityIssue.SUSPICIOUS_VOLUME:
                recommendations.append("Volume spikes may indicate earnings events or data errors")
            elif check.issue_type == QualityIssue.DUPLICATE_TIMESTAMPS:
                recommendations.append("Remove duplicate timestamps and verify data source")
            elif check.issue_type == QualityIssue.STALE_DATA:
                recommendations.append("Update data source - current data is too old for analysis")
        
        if overall_quality == "UNUSABLE":
            recommendations.append("DATA NOT USABLE - Fix critical issues before proceeding")
        elif overall_quality == "POOR":
            recommendations.append("Proceed with caution - data quality is poor")
        elif overall_quality == "ACCEPTABLE":
            recommendations.append("Data is acceptable but may require cleaning")
        
        return recommendations
    
    def clean_dataframe(
        self,
        df: pd.DataFrame,
        report: QualityReport,
    ) -> pd.DataFrame:
        """Clean dataframe based on quality report"""
        df_clean = df.copy()
        
        for check in report.checks:
            if check.issue_type == QualityIssue.DUPLICATE_TIMESTAMPS:
                # Remove duplicates, keep last
                timestamp_col = df_clean.index.name if df_clean.index.name == 'timestamp' else 'timestamp'
                df_clean = df_clean.drop_duplicates(subset=[timestamp_col], keep='last')
            
            elif check.issue_type == QualityIssue.MISSING_VALUES:
                # Forward fill missing values
                df_clean = df_clean.fillna(method='ffill')
                # If still missing, backward fill
                df_clean = df_clean.fillna(method='bfill')
            
            elif check.issue_type == QualityIssue.INCONSISTENT_OHLC:
                # Fix OHLC consistency
                required_cols = ['open', 'high', 'low', 'close']
                if all(col in df_clean.columns for col in required_cols):
                    df_clean['high'] = df_clean[['high', 'open', 'close']].max(axis=1)
                    df_clean['low'] = df_clean[['low', 'open', 'close']].min(axis=1)
        
        return df_clean
