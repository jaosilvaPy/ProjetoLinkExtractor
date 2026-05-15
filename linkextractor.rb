# frozen_string_literal: true

# Link Extractor API — Ruby / Sinatra
# Endpoint: GET /api/<url>
# Cache opcional via variável de ambiente REDIS_URL

require 'sinatra'
require 'open-uri'
require 'nokogiri'
require 'json'
require 'redis'

set :bind, '0.0.0.0'
set :port, 4567

# Conecta ao Redis apenas se REDIS_URL estiver definida
redis_client = nil
redis_url = ENV['REDIS_URL']
redis_client = Redis.new(url: redis_url) if redis_url

get '/api/*' do
  url = params['splat'].first
    url = url.sub(%r{^(https?:)/+}, '\1//')
  # Tenta retornar do cache
  if redis_client
    cached = redis_client.get(url)
    if cached
      content_type :json
      return cached
    end
  end

  # Busca a página e extrai links
  begin
    html = URI.open(url, read_timeout: 15).read
    doc  = Nokogiri::HTML(html)

    links = doc.css('a[href]').map do |a|
      { text: a.text.strip, href: a['href'] }
    end

    result = links.to_json

    redis_client.set(url, result) if redis_client

    content_type :json
    result

  rescue StandardError => e
    status 500
    { error: e.message }.to_json
  end
end