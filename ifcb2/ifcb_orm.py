import os
from datetime import timedelta, datetime
import calendar
import time

import pytz

import sqlalchemy as sqla
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy import and_, or_, desc
from sqlalchemy.sql.expression import func

from oii.times import text2utcdatetime
from oii.resolver import parse_stream
from oii.times import text2utcdatetime

Base = declarative_base()

def datetime2utcdatetime(dt):
    # convert dt without timezone to one in utc
    return datetime.fromtimestamp(calendar.timegm(dt.timetuple()), pytz.utc)

class Bin(Base):
    __tablename__ = 'bins'

    lid = Column(String, primary_key=True)
    sample_time = Column(DateTime(timezone=True))
    skip = Column(Boolean)

    def __init__(self, lid, sample_time, skip=False):
        self.lid = lid
        self.sample_time = sample_time
        self.skip = skip

    def __repr__(self):
        return '<Bin %s>' % self.lid

class File(Base):
    __tablename__ = 'fixity'

    lid = Column(String, ForeignKey('bins.lid'), primary_key=True)
    length = Column(BigInteger)
    filename = Column(String)
    filetype = Column(String, primary_key=True)
    sha1 = Column(String)
    fix_time = Column(DateTime(timezone=True))
    local_path = Column(String)

    bin = relationship('Bin', backref=backref('files',order_by=lid))

    def __init__(self, lid, length, filename, filetype, sha1, fix_time, local_path):
        self.lid = lid
        self.length = length
        self.filename = filename
        self.filetype = filetype
        self.sha1 = sha1
        self.fix_time = fix_time
        self.local_path = local_path

    def __repr__(self):
        return '<File %s %d %s>' % (self.filename, self.length, self.sha1)

def time_range(session, start_time, end_time):
    return session.query(Bin).\
        filter(and_(Bin.sample_time >= start_time, Bin.sample_time <= end_time)).\
        order_by(Bin.sample_time)

demo_end_time = text2utcdatetime('2013-09-20T00:00:00Z')
demo_start_time = demo_end_time - timedelta(hours=2)

# time range demo
def time_range_demo(session):
    print '2 hours worth of bins:'
    for instance in time_range(session, demo_start_time, demo_end_time):
        print instance

# now extend this to show files

def files_demo(session):
    print '2 hours worth of files:'
    for instance in time_range(session, demo_start_time, demo_end_time):
        print instance.files

def data_volume_demo(session):
    print 'data volume per day'
    for row in session.query(func.sum(File.length), func.DATE(Bin.sample_time)).\
        filter(Bin.lid==File.lid).\
        group_by(func.DATE(Bin.sample_time)).\
        order_by(func.DATE(Bin.sample_time)).\
        limit(7):
        print row

def nearest_demo(session):
    ts = '2013-09-10T13:45:22Z'
    somedate = text2utcdatetime(ts)
    n = 5
    print '%d nearest bins to %s' % (n,ts)
    n_before = session.query(Bin).\
        filter(Bin.sample_time <= somedate).\
        order_by(desc(Bin.sample_time)).\
        limit(n)
    min_date = datetime2utcdatetime(n_before[-1].sample_time)
    max_date = somedate + (somedate - min_date)
    n_after = session.query(Bin).\
        filter(and_(Bin.sample_time >= somedate, Bin.sample_time <= max_date)).\
        order_by(Bin.sample_time).\
        limit(n)
    cand = list(n_before) + list(n_after)
    print sorted(cand, key=lambda b: somedate - datetime2utcdatetime(b.sample_time))[:n]

def query_demo(engine):
    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()
    time_range_demo(session)
    files_demo(session)
    data_volume_demo(session)
    nearest_demo(session)
    session.close()

# accession
def list_adcs(time_series,resolver):
    r = parse_stream(resolver)
    for s in r['list_adcs'].resolve_all(time_series=time_series):
        yield s

def list_filesets(time_series,resolver):
    r = parse_stream(resolver)
    for s in list_adcs(time_series,resolver):
        fs = r['fileset'].resolve(pid=s.pid,product='raw',time_series=time_series,day_dir=s.day_dir)
        if fs is not None:
            yield fs

def accession_demo(engine):
    # now accede
    RESOLVER='resolver.xml'
    TIME_SERIES='okeanos'
    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()
    for fs in list_filesets(TIME_SERIES,RESOLVER):
        print fs
        ts = text2utcdatetime(fs.date, fs.date_format)
        b = Bin(fs.lid, ts)
        session.add(b)
        # now make mostly bogus fixity entries
        now = datetime.now()
        paths = [fs.hdr_path, fs.adc_path, fs.roi_path]
        filetypes = ['hdr','adc','roi']
        for path,filetype in zip(paths,filetypes):
            length = os.stat(path).st_size
            file = File(fs.lid, length, os.path.basename(path), filetype, 'abc123', now, path)
            session.add(file)
    session.commit()
    session.close()

def get_sqlite_engine(delete=True):
    # first, toast db
    DB_FILE = 'test.db'
    if(delete):
        try:
            os.remove(DB_FILE)
        except:
            pass
    return sqla.create_engine('sqlite:///%s' % DB_FILE)

if __name__=='__main__':
    wipe = False
    #engine = get_sqlite_engine(delete=wipe)
    engine = sqla.create_engine('postgresql://ifcb:ifcb@localhost/testdb')
    Base.metadata.create_all(engine)
    if wipe: # deleted everything, so need to start
        accession_demo(engine)
    query_demo(engine)