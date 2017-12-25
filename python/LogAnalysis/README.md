<h2>Objective</h2>
This is intended for providing a simple and quick solution to view various types logs based on Search Keywords. It is developed in basic python v2.6 without any additional library. An web interface is also developed using python's basic http server to view the Log Search Data on-line real time. This solution has been implemented for applications running under small/moderate multi-clustered WebLogic platform on unix/linux.
<h2>Functionalities</h2>
<ul>
<li>Provides features to configure/customize various options via property file <code>LogSearchView.properties</code>.</li>
<li>Searches Log Data files either at cluster or individual server level.</li>
<li>Processes log Data Files on local as well as on Remote Machines (via ssh connection).</li>
<li>Merges log data items enclosed with tags spread over multiple lines.</li>
<li>Performs parallel/multi processing on machines with multiple CPUs, if multiprocessing option is enabled on property file <code>LogSearchView.properties</code>.</li>
<li>Sends email messages with HTML output to designated PDLs.</li>
<li>Produces summary output on keyword counts and detail output on Log Data.</li>
<li>Writes output into tab delimited text file.</li>
<li>Provides REST API interface.</li>
</ul>
<h2>Instructions</h2>
<ul>
<li>Copy three files <code>LogSearchView.py</code>, <code>LogSearchViewWeb.py</code> and <code>LogSearchView.properties</code> to the server preferably under a new directory.</li>
<li>Adjust the indentation of <code>LogSearchView.py</code> and <code>LogSearchViewWeb.py</code> if required.</li>
<li>Configure/Customize various options in Property file <code>LogSearchView.properties</code>. Further instructions are provided on the property file for each configuration item.</li>
<li>Execute <code>LogSearchView.py</code> from the server as a script with following arguments:
<ul>
<li><code>environment</code>: <code>itg</code> (For ITG/QA/Test as defined in <code>LogSearchView.properties</code>) or <code>prd</code> (For Production as defined in <code>LogSearchView.properties</code>)</li>
<li><code>cluster</code>: <code>cluster1</code> (Cluster Id as defined in <code>LogSearchView.properties</code>)</li>
<li><code>server</code>: <code>all</code> (For All servers of the Cluster) or <code>server111</code>(Server Id as defined in <code>LogSearchView.properties</code>)</li>
<li><code>log type</code>: <code>managed_server_log</code> (Log Type as defined in <code>LogSearchView.properties</code>)</li>
<li><code>Search Keywords</code>: <code>stderr,error</code> (Search Keywords separated by comma</code>)</li>
<li><code>Search Crieria</code>: <code>all</code> (For Searching all keywords)</code>) or <code>any</code> (For Searching any keywords)</li>
<li>Example: <code>python LogSearchView.py itg cluster1 all managed_server_log stderr,error all</code></li>
</ul>
</li>
<li>Execute <code>LogSearchViewWeb.py</code> to start the Web Interface at port defined in <code>LogSearchView.properties</code> under <code>http_server</code> section:
<ul>
<li>Execute in foreground: <code>python LogSearchViewWeb.py</code></li>
<li>Execute in background (unix/linux): <code>nohup python LogSearchViewWeb.py > LogSearchViewWeb.log &</code></li>
<li>Invoke the URL from the browser <code>http(s)://&lt;host_server_fqdn&gt;:&lt;port&gt;/LogSearchViewWeb</code></li>
<li>Select Input Parameters from Drop-down list, Enter Search Keywords and click <code>Submit</code> button to view the output result</li>
<li>Check REST API from the browser by entering <code>http(s)://&lt;host_server_fqdn&gt;:&lt;port&gt;/LogSearchViewWeb/rest/json/&lt;environment&gt;/&lt;cluster_id&gt;/&lt;server_id&gt;/&lt;log_type&gt;/&lt;search_keywords&gt;/&lt;search_criteria&gt;</code> Example: <code>http(s)://&lt;host_server_fqdn&gt;:&lt;port&gt;/LogSearchViewWeb/rest/json/itg/cluster1/all/managed_server_log/stderr,error/all</code> as defined in <code>LogSearchView.properties</code>. </li>
</ul>
</li>
</ul>
<h2>Assumptions</h2>
<li>Password less <code>ssh</code> connection is already set up between the host machine and other remote machines.</li>
<li>Each <code>Cluster</code> is spread over multiple machines containing multiple servers.</li> 
<li>The Log File Path/location is same on each machine.</li>




