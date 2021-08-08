#imports

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import StructType, StructField, StringType

#create the function for our 311 data
def wrangle_311():
    '''
    wrangle_311 will prep the 311 data like we did in the Spark_Wrangling lesson
    '''
    #intialize spark
    spark = SparkSession.builder.getOrCreate()
    #create schema
    schema = StructType(
        [
            StructField("source_id", StringType()),
            StructField("source_username", StringType()),
        ]
    )
    #bring in dept.csv as dept spark df
    dept = spark.read.csv("data/dept.csv", header=True, inferSchema=True)
    #bring in source.csv as source spark df
    source = spark.read.csv("data/source.csv", header=True, schema=schema)

    #bring in case.csv as spark df
    df = spark.read.csv("data/case.csv", header=True, inferSchema=True)
    
    #rename SLA_due_date as case_due_date
    df = df.withColumnRenamed('SLA_due_date','case_due_date')
    
    #set true if case_closed=='YES', and for case_late=='YES'. False if otherwise
    df = df.withColumn('case_closed', expr('case_closed=="YES"')).withColumn('case_late', expr('case_late="YES"'))
    
    #change council_district into a string
    df = df.withColumn('council_district',col('council_district').cast('string'))
    
    #set how we want our datetime formatted
    fmt = "M/d/yy H:mm"
    #timestamp case_opened_date, case_closed_date, and case_due_date with our specified format
    df = df.withColumn('case_opened_date',to_timestamp('case_opened_date',fmt))\
    .withColumn('case_closed_date', to_timestamp('case_closed_date',fmt))\
    .withColumn('case_due_date', to_timestamp('case_due_date',fmt))

    #lowercase the request address, and removes leading and trailing white space
    df = df.withColumn('request_address', trim(lower(df.request_address)))

    #create a num_weeks_late column that is the number of days late divided by 7
    df = df.withColumn('num_weeks_late', expr('num_days_late/7'))

    #add leading zeroes so that council district has 3 digits, and cast as an int
    df = df.withColumn('council_district',format_string('%03d', col('council_district').cast('int')))

    #make a new column called zipcode, which extracts the digits at the end of the request address string
    df = df.withColumn('zipcode', regexp_extract('request_address', r"(\d+$)",1))

    #create case_age, days_to_closed, and case_lifetime columns.  
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

    #join our data
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

    #return the prepared df
    return df
