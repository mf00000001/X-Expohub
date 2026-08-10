-- 天气查询平台 - 数据库初始化脚本
-- 创建 PostGIS 扩展 + 导入热门城市数据

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;

-- 导入城市数据 (中国主要城市 + 全球热门城市)
INSERT INTO cities (name, name_en, country, country_code, admin1, latitude, longitude, timezone, population, is_hot, priority, owm_city_id, geom)
VALUES
  -- 中国主要城市
  ('北京', 'Beijing', '中国', 'CN', '北京市', 39.9042, 116.4074, 'Asia/Shanghai', 21540000, TRUE, 100, 1816670, ST_SetSRID(ST_MakePoint(116.4074, 39.9042), 4326)),
  ('上海', 'Shanghai', '中国', 'CN', '上海市', 31.2304, 121.4737, 'Asia/Shanghai', 24870000, TRUE, 99, 1796236, ST_SetSRID(ST_MakePoint(121.4737, 31.2304), 4326)),
  ('广州', 'Guangzhou', '中国', 'CN', '广东省', 23.1291, 113.2644, 'Asia/Shanghai', 18680000, TRUE, 98, 1809858, ST_SetSRID(ST_MakePoint(113.2644, 23.1291), 4326)),
  ('深圳', 'Shenzhen', '中国', 'CN', '广东省', 22.5431, 114.0579, 'Asia/Shanghai', 17560000, TRUE, 97, 1795565, ST_SetSRID(ST_MakePoint(114.0579, 22.5431), 4326)),
  ('杭州', 'Hangzhou', '中国', 'CN', '浙江省', 30.2741, 120.1551, 'Asia/Shanghai', 11940000, TRUE, 95, 1808926, ST_SetSRID(ST_MakePoint(120.1551, 30.2741), 4326)),
  ('成都', 'Chengdu', '中国', 'CN', '四川省', 30.5728, 104.0668, 'Asia/Shanghai', 20940000, TRUE, 94, 1815286, ST_SetSRID(ST_MakePoint(104.0668, 30.5728), 4326)),
  ('武汉', 'Wuhan', '中国', 'CN', '湖北省', 30.5928, 114.3055, 'Asia/Shanghai', 12330000, TRUE, 93, 1791247, ST_SetSRID(ST_MakePoint(114.3055, 30.5928), 4326)),
  ('南京', 'Nanjing', '中国', 'CN', '江苏省', 32.0603, 118.7969, 'Asia/Shanghai', 9310000, TRUE, 92, 1799962, ST_SetSRID(ST_MakePoint(118.7969, 32.0603), 4326)),
  ('重庆', 'Chongqing', '中国', 'CN', '重庆市', 29.4316, 106.9123, 'Asia/Shanghai', 32050000, TRUE, 91, 1814906, ST_SetSRID(ST_MakePoint(106.9123, 29.4316), 4326)),
  ('天津', 'Tianjin', '中国', 'CN', '天津市', 39.0842, 117.2009, 'Asia/Shanghai', 13730000, TRUE, 90, 1792947, ST_SetSRID(ST_MakePoint(117.2009, 39.0842), 4326)),
  ('西安', 'Xi''an', '中国', 'CN', '陕西省', 34.3416, 108.9398, 'Asia/Shanghai', 12950000, TRUE, 85, 1790630, ST_SetSRID(ST_MakePoint(108.9398, 34.3416), 4326)),
  ('长沙', 'Changsha', '中国', 'CN', '湖南省', 28.2282, 112.9388, 'Asia/Shanghai', 10050000, TRUE, 84, 1815577, ST_SetSRID(ST_MakePoint(112.9388, 28.2282), 4326)),
  ('厦门', 'Xiamen', '中国', 'CN', '福建省', 24.4798, 118.0894, 'Asia/Shanghai', 5160000, TRUE, 83, 1790645, ST_SetSRID(ST_MakePoint(118.0894, 24.4798), 4326)),
  ('青岛', 'Qingdao', '中国', 'CN', '山东省', 36.0671, 120.3826, 'Asia/Shanghai', 9490000, TRUE, 82, 1797929, ST_SetSRID(ST_MakePoint(120.3826, 36.0671), 4326)),
  ('大连', 'Dalian', '中国', 'CN', '辽宁省', 38.9140, 121.6147, 'Asia/Shanghai', 7450000, TRUE, 81, 1814082, ST_SetSRID(ST_MakePoint(121.6147, 38.9140), 4326)),

  -- 全球热门城市
  ('东京', 'Tokyo', '日本', 'JP', 'Tokyo', 35.6762, 139.6503, 'Asia/Tokyo', 37400000, TRUE, 50, 1850147, ST_SetSRID(ST_MakePoint(139.6503, 35.6762), 4326)),
  ('纽约', 'New York', '美国', 'US', 'New York', 40.7128, -74.0060, 'America/New_York', 18820000, TRUE, 49, 5128581, ST_SetSRID(ST_MakePoint(-74.0060, 40.7128), 4326)),
  ('伦敦', 'London', '英国', 'GB', 'England', 51.5074, -0.1278, 'Europe/London', 14370000, TRUE, 48, 2643743, ST_SetSRID(ST_MakePoint(-0.1278, 51.5074), 4326)),
  ('巴黎', 'Paris', '法国', 'FR', 'Île-de-France', 48.8566, 2.3522, 'Europe/Paris', 11020000, TRUE, 47, 2988507, ST_SetSRID(ST_MakePoint(2.3522, 48.8566), 4326)),
  ('悉尼', 'Sydney', '澳大利亚', 'AU', 'New South Wales', -33.8688, 151.2093, 'Australia/Sydney', 5310000, TRUE, 46, 2147714, ST_SetSRID(ST_MakePoint(151.2093, -33.8688), 4326)),
  ('新加坡', 'Singapore', '新加坡', 'SG', 'Singapore', 1.3521, 103.8198, 'Asia/Singapore', 5700000, TRUE, 45, 1880252, ST_SetSRID(ST_MakePoint(103.8198, 1.3521), 4326)),
  ('首尔', 'Seoul', '韩国', 'KR', 'Seoul', 37.5665, 126.9780, 'Asia/Seoul', 25600000, TRUE, 44, 1835848, ST_SetSRID(ST_MakePoint(126.9780, 37.5665), 4326)),
  ('曼谷', 'Bangkok', '泰国', 'TH', 'Bangkok', 13.7563, 100.5018, 'Asia/Bangkok', 17100000, TRUE, 43, 1609350, ST_SetSRID(ST_MakePoint(100.5018, 13.7563), 4326)),
  ('迪拜', 'Dubai', '阿联酋', 'AE', 'Dubai', 25.2048, 55.2708, 'Asia/Dubai', 3330000, TRUE, 42, 292223, ST_SetSRID(ST_MakePoint(55.2708, 25.2048), 4326)),
  ('香港', 'Hong Kong', '中国', 'HK', 'Hong Kong', 22.3193, 114.1694, 'Asia/Hong_Kong', 7450000, TRUE, 41, 1819729, ST_SetSRID(ST_MakePoint(114.1694, 22.3193), 4326))
ON CONFLICT DO NOTHING;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_cities_name_trgm ON cities USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_cities_geom_gist ON cities USING GIST (geom);
