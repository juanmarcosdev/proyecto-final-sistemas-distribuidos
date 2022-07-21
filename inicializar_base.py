import sqlite3
# DB
conn = sqlite3.connect('caicedonia.db')
conn.execute('''CREATE TABLE cloud_providers
        (id INT PRIMARY KEY NOT NULL,
        count INT NOT NULL,
        link CHAR(256));''')

# GCP
conn.execute("INSERT INTO cloud_providers (id, count, link) \
     VALUES (1, 2, 'http://34.107.141.151:80')");

# AWS
conn.execute("INSERT INTO cloud_providers (id, count, link) \
     VALUES (2, 2, 'http://caicedonia-938704499.us-east-1.elb.amazonaws.com')");

# digital ocean
# conn.execute("INSERT INTO cloud_providers (id, count, link) \
#      VALUES (3, 'Paul', 32, 'California', 20000.00 )");
conn.commit()
conn.close()