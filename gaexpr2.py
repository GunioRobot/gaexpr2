import math
import wsgiref.handlers

from google.appengine.ext import webapp
from google.appengine.ext import search
from google.appengine.ext import db
from google.appengine.ext.webapp.util import run_wsgi_app

class Expression(db.Model):
  affy_id       = db.StringProperty()
  gene_symbol   = db.StringProperty()
  entrezid      = db.StringProperty()
  gene_name     = db.StringProperty()
  evector_day0  = db.FloatProperty()
  evector_day2  = db.FloatProperty()
  evector_day4  = db.FloatProperty()
  evector_day10 = db.FloatProperty()
  ppargox_day0  = db.FloatProperty()
  ppargox_day2  = db.FloatProperty()
  ppargox_day4  = db.FloatProperty()
  ppargox_day10 = db.FloatProperty()


class MainPage(webapp.RequestHandler):
  def get(self):
      
    url = "http://chart.apis.google.com/chart?cht=lxy&chco=1E5692,3E9A3B&chs=200x125&chxt=x,y&chxl=0:|0|2|4|6|8|10|1:|2|4|6|8|10&chds=0,10,2,10,0,10,2,10&chd=t:"

    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write('<html><body>')
    
    # I use the webapp framework to retrieve the keyword
    keyword = self.request.get('keyword')

    if not keyword:
      self.response.out.write("No keyword has been set")
    else:
      # Search the 'Expression' Entity based on our keyword
      query = search.SearchableQuery('Expression')
      query.Search(keyword)
      for result in query.Run():
        # Annotation
        self.response.out.write('<div><pre>')
        self.response.out.write('Affy ID: %s\n'     % result['affy_id'])
        self.response.out.write('Gene Symbol: %s\n' % result['gene_symbol'])
        self.response.out.write('Gene Name: %s\n'   % result['gene_name'])
        self.response.out.write('Entrez Gene: <a href="http://www.ncbi.nlm.nih.gov/sites/entrez?db=gene&cmd=Retrieve&dopt=full_report&list_uids=%s">' % result['entrezid'] + "%s</a>\n" % result['entrezid'])
        self.response.out.write('</pre></div>')
         
        # Graph (Using Google Chart API)
        evector = ",".join([str(result['evector_day' + suffix]) for suffix in ["0", "2", "4", "10"]])
        ppargox = ",".join([str(result['ppargox_day' + suffix]) for suffix in ["0", "2", "4", "10"]])
        graph = url + "0,2,4,10|" + evector + "|0,2,4,10|" + ppargox
        self.response.out.write('<img src="%s">' % graph)
        self.response.out.write('<div><a href="coexpression?keyword=%s">Search coexpression genes</a></div>' % result['affy_id'])

    self.response.out.write('<hr/><div><a href="search">Back</a></div>')
    self.response.out.write('</body></html>')
    
class IdSearchForm(webapp.RequestHandler):
  def get(self):
    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write("""
      <html>
        <body>
          <h1>Gene Expression Database</h1>
          <form action="/" method="get">
            <div>
              Keyword: <input type="text" name="keyword" rows="1" cols="12">
              <input type="submit" value="Search"> (ex. 100005_at, Traf4)
            </div>
          </form>
          <hr/>
          <a href="http://itoshi.tv/">Itoshi NIKAIDO, Ph. D.</a>, dritoshi at gmail dot com
          <div>
            <img src="http://code.google.com/appengine/images/appengine-silver-120x30.gif" alt="Powered by Google App Engine" />
          </div>
        </body>
      </html>""")

class Coexpression(webapp.RequestHandler):
  def mean(self, exprs):
    mean = 0.0
    for expr in exprs:
      mean += expr
    return mean / len(exprs)

  def sd(self, deviations):
    sd = 0.0
    for deviation in deviations:
      sd += deviation**2
    return math.sqrt(sd)

  def deviations(self, exprs, mean):
    return [expr - mean for expr in exprs]

  def covariance(self, target_deviations, subject_deviations):
    covar = 0.0
    for target, subject in zip(target_deviations, subject_deviations):
      covar += target * subject
    return covar

  def get(self):

    # Start of calcation coexpression gene
    # I use the webapp framework to retrieve the keyword
    keyword = self.request.get('keyword')

    if not keyword:
      #self.response.out.write("No keyword has been set")
      result = "No keyword has been set"
    else:
      # Search the 'Expression' Entity based on our keyword
      # get log2 ratio expressions of target gene

      query = search.SearchableQuery('Expression')
      query.Search(keyword)
      for result in query.Run():
         target_gene_exprs = [result['ppargox_day' + suffix]-result['evector_day' + suffix] for suffix in ["0", "2", "4", "10"]]

      # get log2 ratio expressions of subject genes
      # I will separate Cor class following the code.
      coexpression_genes = {}

      target_mean       = self.mean(target_gene_exprs)
      target_deviations = self.deviations(target_gene_exprs, target_mean)
      target_sd         = self.sd(target_deviations)

      subject_genes = db.GqlQuery("SELECT * FROM Expression")
      for subject_gene in subject_genes:
        # so bad code ;-)
        subject_gene_exprs = [subject_gene.ppargox_day0  - subject_gene.evector_day0,
                              subject_gene.ppargox_day2  - subject_gene.evector_day2,
                              subject_gene.ppargox_day4  - subject_gene.evector_day4,
                              subject_gene.ppargox_day10 - subject_gene.evector_day10]

        # calc corr.
        subject_mean       = self.mean(subject_gene_exprs)
        subject_deviations = self.deviations(subject_gene_exprs, subject_mean)
        subject_sd         = self.sd(subject_deviations)

        covar = self.covariance(target_deviations, subject_deviations)
        cor = covar / (subject_sd * target_sd)

        # filtering
        if math.fabs(cor) >= 0.9:
          coexpression_genes[subject_gene.affy_id] = [subject_gene.gene_symbol, cor]
        
      # too long...
      result = "".join(['<tr><td><a href="/?search&keyword=' + affy_id + '">' + affy_id + '</a></td><td>' + data[0] + '</td><td>' + str(data[1]) + '</td></tr>' for affy_id, data in coexpression_genes.iteritems()])
    # End of calcation coexpression gene


    # output html 
    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write('<html><body>')
    self.response.out.write("""
          <h1>Gene Expression Database</h1>
          """)
    self.response.out.write('<table>')
    self.response.out.write('<tr><th>Affymetrix ID</th><th>Gene Symbol</th><th>Correlation Coefficient</th></tr>')
    self.response.out.write(result)
    self.response.out.write('</table>')
    self.response.out.write("""
          <hr/>
          <a href="http://itoshi.tv/">Itoshi NIKAIDO, Ph. D.</a>, dritoshi at gmail dot com
          <div>
            <img src="http://code.google.com/appengine/images/appengine-silver-120x30.gif" alt="Powered by Google App Engine" />
          </div>
        </body>
      </html>""")


application = webapp.WSGIApplication(
                                     [('/', MainPage),
                                      ('/search', IdSearchForm),
                                      ('/coexpression', Coexpression)],
                                     debug=True)

def main():                                       
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
