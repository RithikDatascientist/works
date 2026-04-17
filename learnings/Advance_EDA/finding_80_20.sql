select * from sales_orders 
limit 10


select sum(Sales) * 0.8 from sales_orders

with product_sales_table as (
select product_id, sum(sales) as product_sales
from sales_orders 
group by product_id 
)
,
final_df as (
select product_id, product_sales,
sum(product_sales) over( order by product_sales desc rows between unbounded preceding and 0 preceding ) as running_sales,
 0.8  * sum(product_sales) over() as eighty_pct_Sales
from product_sales_table
group by product_id,product_sales
)

select * from final_df
where running_sales <= eighty_pct_sales