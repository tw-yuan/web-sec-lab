FROM php:8.2-apache

# Allow .htaccess overrides
RUN sed -i 's/AllowOverride None/AllowOverride All/' /etc/apache2/sites-available/000-default.conf && \
    a2enmod rewrite

# PHP upload settings
RUN echo "upload_max_filesize = 10M\npost_max_size = 10M\nfile_uploads = On" \
    >> /usr/local/etc/php/php.ini

COPY src/ /var/www/html/

# Uploads directory must be writable by Apache
RUN mkdir -p /var/www/html/uploads && \
    chown -R www-data:www-data /var/www/html/uploads && \
    chmod 755 /var/www/html/uploads

# Flag outside webroot — students read it via webshell
ENV FLAG=AIS3{f1l3_upl04d_byp4ss_RCE_pwn3d}
RUN echo "${FLAG}" > /flag.txt && chmod 644 /flag.txt

EXPOSE 80
