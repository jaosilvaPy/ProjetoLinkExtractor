FROM ruby:3.3-alpine

LABEL description="Link Extractor API — Ruby/Sinatra"

WORKDIR /app

# Dependências nativas para Nokogiri
RUN apk add --no-cache \
    build-base \
    libxml2-dev \
    libxslt-dev

# Instala gems
RUN gem install \
    sinatra \
    nokogiri:1.16.7 \
    redis:5.3.0 \
    rackup \
    webrick \
    --no-document

COPY linkextractor.rb .

EXPOSE 4567

CMD ["ruby", "linkextractor.rb"]