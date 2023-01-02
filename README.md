# 49ja Game Data

## Introduction
Welcome to 49ja Game data! This application is designed to help players of the bet9ja 49ja game make more informed decisions by providing access to historical data.

This application gathers data from the bet9ja 49ja game website through web scraping using selenium and presents the data in easy-to-read tables and charts. You can view data for time intervals, and compare data from different periods to see trends and patterns.

We hope that our application will be a useful tool for players looking to analyze and understand the bet9ja 49ja game data.

## Installation
1. To use this application on your personal computer (PC), you must have python3 and postgreSQL installed.
If you have not installed them, follow the link below setup python and postgreSQL for your pc.
* [Python](https://www.digitalocean.com/community/tutorials/install-python-windows-10) - Windows
* [PostgreSQl](https://phoenixnap.com/kb/install-postgresql-windows) - Windows
* [PostgreSQL](https://www.digitalocean.com/community/tutorials/how-to-install-postgresql-on-ubuntu-20-04-quickstart) - Linux


2. After installation create a new database using the steps [here](https://www.microfocus.com/documentation/idol/IDOL_12_0/MediaServer/Guides/html/English/Content/Getting_Started/Configure/_TRN_Set_up_PostgreSQL.htm). Take note of the database name and your password to postgresql

3. Copy and paste the command below into your terminal to clone the repository into your machine.

```
$ git clone https://github.com/BenFaruna/49ja_game
```

4. Navigate into the project directory from your terminal using the command.
```
$ cd 49ja_game
```

5. (optional) You can create a virtual environment by following the steps outlined [here](https://www.freecodecamp.org/news/how-to-setup-virtual-environments-in-python/). Activate the virtual environment.

6. Install packages needed for the application to run using the command
```
49ja_game$ pip install -r requirements.txt
```

7. Add your database url as an environmental variable.

On Windows using powershell
```ps
ps 49ja_game> $env:DB_URL='postgresql://postgres:<database-password>@localhost/<database-name>' 
```

On Linux
```bash
49ja_game$ DB_URL='postgresql://postgres:neodynamics@localhost/49ja_data_db'
```

After adding the database url as an environmental variable, you can start either the automation script for gathering data ([main.py](./main.py)) or the web application that shows the data in the application ([app.py](./app.py)) or both at the same time using two terminals. When using two terminals, step 7 must be done for both terminals.

8. Start the application
```sh
49ja_game$ python main.py
```
```sh
49ja_game$ python app.py
```
9. You can view the data by accessing your database directly or opening the link http://localhost:5000 on your browser.

## Usage
