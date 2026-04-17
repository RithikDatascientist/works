
select * from person
select * from friend


select f.personid, sum(p.score) as total_score, count(1) as no_of_frnd, string_agg(distinct p.name, ',') as frnds_name from friend f
inner join person p
on f.friendid = p.personid 
group by f.personid 
having sum(p.score) >= 100


select * from Trips
select * from Users

select t.request_at , count(case when t.status in ('cancelled_by_client' , 'cancelled_by_driver') then 1 else null end) as cancel_count,
count(1) as total_trips,  1.0 * count(case when t.status in ('cancelled_by_client' , 'cancelled_by_driver') then 1 else null end)/ count(1) * 100 as cancel_rate
from Trips t
inner join Users c 
on t.client_id  = c.users_id
inner join Users d 
on t.driver_id = d.users_id 
where c.banned = 'No' and d.banned = 'No'
group by t.request_at




select * from players
select * from matches

with players_score as  (
select first_player as player_id, first_score as score from matches 
union all 
select second_player as player_id, second_score as score from matches 
),
score_details as (
select player_id , sum(score) as total_score from players_score
group by player_id
),
final_rank as (
select sd.player_id, rank() over(partition by group_id order by sd.total_score desc, sd.player_id ASC) as rnk , p.group_id, sd.total_Score from score_details sd 
join players p 
on sd.player_id = p.player_id 
)
select * from final_rank 
where rnk =1


select * from orders
select * from users 
select * from items

with sales_orders as (
select *, rank() over(partition by seller_id order by order_date asc) as rn
from orders
)
select u.user_id,u.favorite_brand,i.item_brand, case when u.favorite_brand = i.item_brand then 'Yes' else 'N0' end as selled_favorite_product 
from users u
left join sales_orders s on s.seller_id = u.user_id and rn = 2
left join items i on i.item_id = s.item_id




select user_id,spend_date,max(platform), sum(amount) from spending
group by spend_date,user_id having count(distinct platform) = 1

select * from spending