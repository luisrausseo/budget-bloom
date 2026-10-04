update public.categories
set name = case name
    when 'Uncategorized' then '❓ Uncategorized'
    when 'Housing' then '🏠 Housing'
    when 'Rent' then '🏘️ Rent'
    when 'Mortgage' then '🏡 Mortgage'
    when 'Credit Card' then '💳 Credit Card'
    when 'Water' then '💧 Water'
    when 'Electricity' then '⚡ Electricity'
    when 'Gas' then '🔥 Gas'
    when 'Cable' then '📺 Cable'
    when 'Internet' then '🌐 Internet'
    when 'Phone' then '📱 Phone'
    when 'Groceries' then '🛒 Groceries'
    when 'Dining Out' then '🍽️ Dining Out'
    when 'Transportation' then '🚗 Transportation'
    when 'Insurance' then '🛡️ Insurance'
    when 'Healthcare' then '🩺 Healthcare'
    when 'Childcare' then '🧸 Childcare'
    when 'Education' then '🎓 Education'
    when 'Entertainment' then '🎬 Entertainment'
    when 'Subscriptions' then '🔁 Subscriptions'
    when 'Savings' then '💰 Savings'
    when 'Debt Payment' then '📉 Debt Payment'
    when 'Income' then '💵 Income'
    when 'Salary' then '💵 Salary'
    when 'Other Income' then '🪙 Other Income'
    when 'Other' then '📦 Other'
end
where name in (
    'Uncategorized', 'Housing', 'Rent', 'Mortgage', 'Credit Card', 'Water',
    'Electricity', 'Gas', 'Cable', 'Internet', 'Phone', 'Groceries',
    'Dining Out', 'Transportation', 'Insurance', 'Healthcare', 'Childcare',
    'Education', 'Entertainment', 'Subscriptions', 'Savings', 'Debt Payment',
    'Income', 'Salary', 'Other Income', 'Other'
);
