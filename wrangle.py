from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import StructType, StructField, StringType

def wrangle_311():
    spark = SparkSession.builder.getOrCreate()
    schema = StructType(
        [
            StructField("source_id", StringType()),
            StructField("source_username", StringType()),
        ]
    )

    dept = spark.read.csv("data/dept.csv", header=True, inferSchema=True)
    source = spark.read.csv("data/source.csv", header=True, schema=schema)

    df = spark.read.csv("data/case.csv", header=True, inferSchema=True)
    df = df.withColumnRenamed('SLA_due_date','case_due_date')
    df = df.withColumn('case_closed', expr('case_closed=="YES"')).withColumn('case_late', expr('case_late="YES"'))
    df = df.withColumn('council_district',col('council_district').cast('string'))

    fmt = "M/d/yy H:mm"

    df = df.withColumn('case_opened_date',to_timestamp('case_opened_date',fmt))\
    .withColumn('case_closed_date', to_timestamp('case_closed_date',fmt))\
    .withColumn('case_due_date', to_timestamp('case_due_date',fmt))

    df = df.withColumn('request_address', trim(lower(df.request_address)))

    df = df.withColumn('num_weeks_late', expr('num_days_late/7'))

    df = df.withColumn('council_district',format_string('%03d', col('council_district').cast('int')))

    df = df.withColumn('zipcode', regexp_extract('request_address', r"(\d+$)",1))

    df = (
        df.withColumn(
            "case_age", datediff(current_timestamp(), "case_opened_date")
        )
        .withColumn(
            "days_to_closed", datediff("case_closed_date", "case_opened_date")
        )
        .withColumn(
            "case_lifetime",
            when(expr("! case_closed"), col("case_age")).otherwise(
                col("days_to_closed")
            ),
        )
    )

    df = (
        df
        # left join on dept_division
        .join(dept, "dept_division", "left")
        # drop all the columns except for standardized name, as it has much fewer unique values
        .drop(dept.dept_division)
        .drop(dept.dept_name)
        .drop(df.dept_division)
        .withColumnRenamed("standardized_dept_name", "department")
        # convert to a boolean
        .withColumn("dept_subject_to_SLA", col("dept_subject_to_SLA") == "YES")
    )

    return df
