sudo ufw status numbered
sudo ufw all 22/tcp
sudo ufw allow 22/tcp
sudo ufw enable
exit
sudo ufw status numbered
sudo ufw allow 80
sudo ufw allow 443
sudo ufw status numbered
sudo nano /etc/ssh/sshd_config
sudo ufw enablesudo apt-get update
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo   "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" |   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable docker
sudo systemctl status docker
sudo usermod -aG docker alpha
docker ps
exit
docker ps
sudo docker volume create portainer_data
sudo docker network create banker_local_nw
y
sudo docker ps
sudo docker network inspect local_banker_nw
sudo docker network inspect banker_local_nw
sudo apt install nginx
sudo ufw status numbered
sudo apt install nginx -y
sudo systemctl start nginx
sudo systemctl enable nginx
sudo systemctl status nginx
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d nexmediaai.com -d www.nexmediaai.com -d admin.nexmediaai.com
sudo certbot renew --dry-run
cd /home/alpha
mkdir nexmediaai-project
cd nexmediaai-project/
sudo apt install make
make
sudo docker ps
sudo systemctl restart  nginx
sudo systemctl status nginx
sudo systemctl restart  nginx
sudo systemctl status nginx
sudo systemctl restart  nginx
sudo systemctl status nginx
nginx -t
sudo systemctl restart  nginx
sudo systemctl status nginx
sudo nginx -t
sudo systemctl restart  nginx
sudo rm /etc/nginx/sites-available/default
sudo nano /etc/nginx/sites-available/default
sudo nginx -t
sudo systemctl restart  nginx
make build
ls
docker compose -f local.yml run --rm api python manage.py shell
sudo nano /etc/nginx/sites-available/default
sudo systemctl restart  nginx
docker compose -f local.yml run --rm api python manage.py loadplans
docker compose -f local.yml run --rm api python manage.py load_plans
make superuser
exit
ls
cd nexmediaai-project/
make build
systemctl restart nginx.service 
MAKE UP
make up
make down
make up
sudo apt update
sudo apt install wireguard
cd /etc/wireguard
login
login root
cd nexmediaai-project/
make up
make down]
make down
make up
ls
cd nexmediaai-project/
make down
ls
make down
make up
make build
make down
make up
make build
make up
make down
make up
make builf
make build
make down
make up
make makemigrations
make migrate
make up
make down
make up
make down
make up
cd nexmediaai-project/
make down
cd nexmediaai-project/
make up
make up
cd nexmediaai-project/
make up
make down
cd nexmediaai-project/
ls
cd web_apps/video_caption/
ls
nano views.py 
cd ../..
make up
ls
cd nexmediaai-project/
cd web_apps/video_caption/
nano views.py 
make down
cd ../..
make down
make up
cd nexmediaai-project/web_apps/video_caption/
nano views.py 
cd ../..
make up
make down
make up
ls
cd nexmediaai-project/web_apps/video_caption/
nano views.py 
cd ..
make down
cd nexmediaai-project/
MAKE UP
make up
make makemigrations
cd nexmediaai-project/
make makemigrations
make migrate
cd nexmediaai-project/
make up
cd nexmediaai-project/
make up
