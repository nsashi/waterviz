#!/usr/bin/env python
import requests
import redis
import psycopg2
import psycopg2.extras
import numpy as np
import scipy.stats
import sys

conn = psycopg2.connect("dbname='rivers' user='nelson' host='localhost' password='NONE'")

states = [
  {"abbrev":"AK", "fips":"02","name":"ALASKA"},
  {"abbrev":"AL", "fips":"01","name":"ALABAMA"},
  {"abbrev":"AR", "fips":"05","name":"ARKANSAS"},
  {"abbrev":"AS", "fips":"60","name":"AMERICAN SAMOA"},
  {"abbrev":"AZ", "fips":"04","name":"ARIZONA"},
  {"abbrev":"CA", "fips":"06","name":"CALIFORNIA"},
  {"abbrev":"CO", "fips":"08","name":"COLORADO"},
  {"abbrev":"CT", "fips":"09","name":"CONNECTICUT"},
  {"abbrev":"DC", "fips":"11","name":"DISTRICT OF COLUMBIA"},
  {"abbrev":"DE", "fips":"10","name":"DELAWARE"},
  {"abbrev":"FL", "fips":"12","name":"FLORIDA"},
  {"abbrev":"GA", "fips":"13","name":"GEORGIA"},
  {"abbrev":"GU", "fips":"66","name":"GUAM"},
  {"abbrev":"HI", "fips":"15","name":"HAWAII"},
  {"abbrev":"IA", "fips":"19","name":"IOWA"},
  {"abbrev":"ID", "fips":"16","name":"IDAHO"},
  {"abbrev":"IL", "fips":"17","name":"ILLINOIS"},
  {"abbrev":"IN", "fips":"18","name":"INDIANA"},
  {"abbrev":"KS", "fips":"20","name":"KANSAS"},
  {"abbrev":"KY", "fips":"21","name":"KENTUCKY"},
  {"abbrev":"LA", "fips":"22","name":"LOUISIANA"},
  {"abbrev":"MA", "fips":"25","name":"MASSACHUSETTS"},
  {"abbrev":"MD", "fips":"24","name":"MARYLAND"},
  {"abbrev":"ME", "fips":"23","name":"MAINE"},
  {"abbrev":"MI", "fips":"26","name":"MICHIGAN"},
  {"abbrev":"MN", "fips":"27","name":"MINNESOTA"},
  {"abbrev":"MO", "fips":"29","name":"MISSOURI"},
  {"abbrev":"MS", "fips":"28","name":"MISSISSIPPI"},
  {"abbrev":"MT", "fips":"30","name":"MONTANA"},
  {"abbrev":"NC", "fips":"37","name":"NORTH CAROLINA"},
  {"abbrev":"ND", "fips":"38","name":"NORTH DAKOTA"},
  {"abbrev":"NE", "fips":"31","name":"NEBRASKA"},
  {"abbrev":"NH", "fips":"33","name":"NEW HAMPSHIRE"},
  {"abbrev":"NJ", "fips":"34","name":"NEW JERSEY"},
  {"abbrev":"NM", "fips":"35","name":"NEW MEXICO"},
  {"abbrev":"NV", "fips":"32","name":"NEVADA"},
  {"abbrev":"NY", "fips":"36","name":"NEW YORK"},
  {"abbrev":"OH", "fips":"39","name":"OHIO"},
  {"abbrev":"OK", "fips":"40","name":"OKLAHOMA"},
  {"abbrev":"OR", "fips":"41","name":"OREGON"},
  {"abbrev":"PA", "fips":"42","name":"PENNSYLVANIA"},
  {"abbrev":"PR", "fips":"72","name":"PUERTO RICO"},
  {"abbrev":"RI", "fips":"44","name":"RHODE ISLAND"},
  {"abbrev":"SC", "fips":"45","name":"SOUTH CAROLINA"},
  {"abbrev":"SD", "fips":"46","name":"SOUTH DAKOTA"},
  {"abbrev":"TN", "fips":"47","name":"TENNESSEE"},
  {"abbrev":"TX", "fips":"48","name":"TEXAS"},
  {"abbrev":"UT", "fips":"49","name":"UTAH"},
  {"abbrev":"VA", "fips":"51","name":"VIRGINIA"},
  {"abbrev":"VI", "fips":"78","name":"VIRGIN ISLANDS"},
  {"abbrev":"VT", "fips":"50","name":"VERMONT"},
  {"abbrev":"WA", "fips":"53","name":"WASHINGTON"},
  {"abbrev":"WI", "fips":"55","name":"WISCONSIN"},
  {"abbrev":"WV", "fips":"54","name":"WEST VIRGINIA"},
  {"abbrev":"WY", "fips":"56","name":"WYOMING"}
]

do_these_states = ["AL","AZ","AR","CA","CO","CT","DE","FL","GA","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]
states          = filter(lambda x: x['abbrev'] in do_these_states,states)


cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

cur.execute("SELECT site_no, array_to_string(array_agg(ave), ',') AS yearly_ave FROM (SELECT site_no, ave FROM gage_smooth WHERE month=13 AND year>=1985 ORDER BY site_no,ave) a GROUP BY site_no")
historic_data = {}
for i in cur.fetchall():
  temp = np.fromstring(i['yearly_ave'], dtype=float, sep=',')
  historic_data[i['site_no']] = temp

cur.execute("SELECT source_fea AS gaugecode,reachcode FROM gageloc")
#Fetches a list of, e.g: {'gaugecode': '01109070', 'reachcode': '01090004001157'}
#Builds a hashmap relating gauges to the reach they are on
gauges_to_huc8 = {}
for gauge in cur.fetchall():
  gauges_to_huc8[gauge['gaugecode']] = gauge['reachcode'][0:8]

agg_reach_data = {}
agg_gauge_data = {}

#See: http://waterservices.usgs.gov/rest/IV-Service.html#Multiple for API info
def getData(state):
  print("Gathering data for %s" % (state))
  url     = "http://waterservices.usgs.gov/nwis/iv/"
  #options = {"format":"json","stateCd":state,"parameterCd":"00060,00065","siteStatus":"active","startDT":'2011-04-28','endDT':'2011-09-09'}
  options = {"format":"json","stateCd":state,"parameterCd":"00060,00065","siteStatus":"active"}
  resp    = requests.get(url,params=options)
  if resp.status_code!=200:
    pass
  resp = resp.json()

  had_no_reach_count = 0

  for s in resp['value']['timeSeries']:
    if len(s['variable']['variableCode'])>1:
      print s['variable']['variableCode']
      print "More variables!"
    if len(s['sourceInfo']['siteCode'])>1:
      print "More sites!"
    try:
      site_code     = s['sourceInfo']['siteCode'][0]['value']
      variable_code = s['variable']['variableCode'][0]['value']
      #variable_code = translate_variable_code[variable_code]
      timestamp     = s['values'][0]['value'][0]['dateTime']
      value         = max([float(x['value']) for x in s['values'][0]['value']])

      if not site_code in gauges_to_huc8:
        sys.stderr.write("No reach found for %s\n" % (site_code))
        had_no_reach_count += 1
        continue
      reach_code = gauges_to_huc8[site_code]

      if not site_code in agg_gauge_data:
        agg_gauge_data[site_code] = {'site_code':site_code,'dvalue':None,'svalue':None,'drank':None}
      if not reach_code in agg_reach_data:
        agg_reach_data[reach_code] = {'huc8':reach_code,'dvalue':[],'svalue':[],'drank':[]}

      reach_obj = agg_reach_data[reach_code]
      gauge_obj = agg_gauge_data[site_code]
      if variable_code=='00065': #Stage
        reach_obj['svalue'].append(value)
        gauge_obj['svalue'] = value
      elif variable_code=='00060': #Discharge
        reach_obj['dvalue'].append(value)
        gauge_obj['dvalue'] = value
        if site_code in historic_data:
          gauge_obj['drank'] = scipy.stats.percentileofscore(historic_data[site_code],value)
          reach_obj['drank'].append(gauge_obj['drank'])
    except:
      pass

  print "%d of %d stations had no associated reaches." % (had_no_reach_count, len(resp['value']['timeSeries']))



for state in states:
  data = getData(state['abbrev'])

for k,v in agg_reach_data.iteritems():
  if len(v['svalue'])>0:
    v['svalue'] = np.average(v['svalue'])
  else:
    v['svalue'] = None

  if len(v['dvalue'])>0:
    v['dvalue'] = np.average(v['dvalue'])
  else:
    v['dvalue'] = None

  if len(v['drank'])>0:
    v['drank'] = np.average(v['drank'])
  else:
    v['drank'] = None

cur.execute("CREATE TEMP TABLE tmp ON COMMIT DROP AS SELECT * FROM gauge_summary WITH NO DATA")
#cur.execute("CREATE TABLE tmp   AS SELECT * FROM gauge_data with no data")
#cur.executemany("""INSERT INTO tmp(huc8,dvalue,svalue,drank,jday) VALUES (%(huc8)s, %(dvalue)s, %(svalue)s, %(drank)s, now()::date-'1970-01-01'::date)""", agg_reach_data)

#Convert agg_reach_data into a list suitable for mass insertion into the db
agg_gauge_data = [v for k,v in agg_gauge_data.iteritems()]

cur.executemany("""
WITH new_values (site_code,dvalue,svalue,drank,jday) AS (
  VALUES (%(site_code)s, CAST(%(dvalue)s AS REAL), CAST(%(svalue)s AS REAL), CAST(%(drank)s AS REAL), now()::date-'1970-01-01'::date)
),
upsert AS
(
    UPDATE gauge_summary m
        SET dvalue = GREATEST(m.dvalue,nv.dvalue),
            svalue = GREATEST(m.svalue,nv.svalue),
            drank  = GREATEST(m.drank, nv.drank )
    FROM new_values nv
    WHERE m.site_code = nv.site_code AND m.jday=nv.jday
    RETURNING m.*
)
INSERT INTO gauge_summary (site_code,dvalue,svalue,drank,jday)
SELECT site_code,dvalue,svalue,drank,jday
FROM new_values
WHERE NOT EXISTS (SELECT 1
                  FROM upsert up
                  WHERE up.site_code = new_values.site_code AND up.jday = new_values.jday)
""", agg_gauge_data)

conn.commit()









cur.execute("CREATE TEMP TABLE tmp ON COMMIT DROP AS SELECT * FROM reach_summary WITH NO DATA")
#cur.execute("CREATE TABLE tmp   AS SELECT * FROM gauge_data with no data")
#cur.executemany("""INSERT INTO tmp(huc8,dvalue,svalue,drank,jday) VALUES (%(huc8)s, %(dvalue)s, %(svalue)s, %(drank)s, now()::date-'1970-01-01'::date)""", agg_reach_data)

#Convert agg_reach_data into a list suitable for mass insertion into the db
agg_reach_data = [v for k,v in agg_reach_data.iteritems()]

cur.executemany("""
WITH new_values (huc8,dvalue,svalue,drank,jday) AS (
  VALUES (%(huc8)s, CAST(%(dvalue)s AS REAL), CAST(%(svalue)s AS REAL), CAST(%(drank)s AS REAL), now()::date-'1970-01-01'::date)
),
upsert AS
(
    UPDATE reach_summary m
        SET dvalue = GREATEST(m.dvalue,nv.dvalue),
            svalue = GREATEST(m.svalue,nv.svalue),
            drank  = GREATEST(m.drank, nv.drank )
    FROM new_values nv
    WHERE m.huc8 = nv.huc8 AND m.jday=nv.jday
    RETURNING m.*
)
INSERT INTO reach_summary (huc8,dvalue,svalue,drank,jday)
SELECT huc8,dvalue,svalue,drank,jday
FROM new_values
WHERE NOT EXISTS (SELECT 1
                  FROM upsert up
                  WHERE up.huc8 = new_values.huc8 AND up.jday = new_values.jday)
""", agg_reach_data)


conn.commit()