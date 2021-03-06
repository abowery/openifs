#! /usr/bin/python2.7

# Script to submit OpenIFS workunits

# This script has been written by Andy Bowery (Oxford University, 2019)

if __name__ == "__main__":

    #import fileinput
    import os, zipfile, shutil, datetime, calendar, math, MySQLdb, fcntl
    import json, argparse, os, subprocess, time, sys, xml.etree.ElementTree as ET
    from email.mime.text import MIMEText
    from subprocess import Popen, PIPE
    from xml.dom import minidom
    from shutil import copyfile

    # use argparse to read in the options from the shell command line
    parser = argparse.ArgumentParser()
    parser.add_argument("--app_name",help="application name",default="openifs")
    options = parser.parse_args()
    print "Application name: "+options.app_name

    # Check if a lockfile is present from an ongoing submission
    lockfile='/tmp/lockfile'
    print "Waiting for lock...",
    f=open(lockfile,'w')
    fcntl.lockf(f,fcntl.LOCK_EX)
    print "got lock\n"

    project_dir = <PROJECT_DIRECTORY>
    primary_db = <PRIMARY_DATABASE>
    secondary_db = <SECONDARY_DATABASE>
    input_directory = project_dir+ <INCOMING_XML_FOLDER>

    # Set the regionid as global
    regionid = 15

    # Set the number of upload files
    number_of_uploads = 1

    # Set the max_results_per_workunit
    max_results_per_workunit = 1

    # Set the flops factor
    flops_factor = 2386500000000


    # Parse the project config xml file
    xmldoc3 = minidom.parse(project_dir+'config.xml')
    configs = xmldoc3.getElementsByTagName('config')
    for config in configs:
      db_host = str(config.getElementsByTagName('db_host')[0].childNodes[0].nodeValue)
      db_user = str(config.getElementsByTagName('db_user')[0].childNodes[0].nodeValue)
      db_passwd = str(config.getElementsByTagName('db_passwd')[0].childNodes[0].nodeValue)
      db_name = str(config.getElementsByTagName('db_name')[0].childNodes[0].nodeValue)

    # Open cursor and connection to primary_db
    db = MySQLdb.connect(db_host,db_user,db_passwd,primary_db,port=33001)
    cursor = db.cursor()

    # Find the appid
    query = """select id from app where name = '%s'""" % (options.app_name)
    cursor.execute(query)
    appid = cursor.fetchone()[0]

    print "appid: "+str(appid)

    # Find the last workunit id
    query = 'select max(id) from workunit'
    cursor.execute(query)
    last_wuid = cursor.fetchone()

    # Close cursor and connection to primary_db
    cursor.close()
    db.close()

    # Catch the case of no workunits in the database
    if last_wuid[0] == None:
       last_id=0
    else:
       last_id=last_wuid[0]
    print "Last workunit id: "+str(last_id)
    wuid=last_id

    # Open cursor and connection to secondary_db
    db = MySQLdb.connect(db_host,db_user,db_passwd,secondary_db,port=33001)
    cursor = db.cursor()

    # Find the last batch id
    query = 'select max(id) from BATCH_TABLE'
    cursor.execute(query)
    last_batchid = cursor.fetchone()

    # Catch the case of no batches in the database
    if last_batchid[0] == None:
      last_id_2=0
    else:
      last_id_2=last_batchid[0]
    print "Last batch id: "+str(last_id_2)
    batchid=last_id_2

    print ""
    print "--------------------------------------"
    print "Starting submission run: "+str(datetime.datetime.now())
    print "--------------------------------------"
    print ""
    
    # Iterate over the xmlfile in the input directory
    for input_xmlfile in os.listdir(input_directory):
      if input_xmlfile.endswith(".xml"):
        print "--------------------------------------"
        print "Processing input xmlfile: "+str(input_xmlfile)
        print ""

        # Parse the input xmlfile
        xmldoc = minidom.parse(input_directory+"/"+input_xmlfile)

        # Iterate over the batches in the xmlfile
        batches = xmldoc.getElementsByTagName('batch')
        for batch in batches:

          batchid = batchid+1
          number_of_workunits = 0

          # Check model_class and if it is not openifs then exit loop and move on to the next xml file
          model_class = str(batch.getElementsByTagName('model_class')[0].childNodes[0].nodeValue)
          print "model_class: "+model_class
          non_openifs_class = False
          if model_class != 'openifs': 
            non_openifs_class = True
            print "model class is not openifs, moving on to the next xml file\n"
            break

          model_config = str(batch.getElementsByTagName('model_config')[0].childNodes[0].nodeValue)
          print "model_config: "+model_config

          upload_infos = batch.getElementsByTagName('upload_info')
          for upload_info in upload_infos:
            upload_handler = str(upload_info.getElementsByTagName('upload_handler')[0].childNodes[0].nodeValue)
            result_template_prefix = str(upload_info.getElementsByTagName('result_template_prefix')[0].childNodes[0].nodeValue)
            result_template = result_template_prefix+'_n'+str(number_of_uploads)+'.xml'
            print "upload_handler: "+upload_handler
            print "result_template: "+project_dir+result_template

          # If result template does not exist, then create a new template
          if not (os.path.exists(project_dir+result_template)):
            output_string="<output_template>\n" +\
              "<file_info>\n" +\
              "  <name><OUTFILE_1/>.zip</name>\n" +\
              "  <generated_locally/>\n" +\
              "  <max_nbytes>100000000000000</max_nbytes>\n" +\
              "  <url>"+upload_handler+"</url>\n" +\
              "</file_info>\n" +\
              "<result>\n" +\
              "   <file_ref>\n" +\
              "     <file_name><OUTFILE_1/>.zip</file_name>\n" +\
              "     <open_name>upload_file_1.zip</open_name>\n" +\
              "     <no_delete/>\n" +\
              "   </file_ref>\n" +\
              "</result>\n" +\
              "</output_template>"

            OUTPUT=open(project_dir+result_template,"w")
            # Create the result_template
            print >> OUTPUT, output_string
            OUTPUT.close()

          # Set the server_cgi from the upload_handler string
          server_cgi = upload_handler[:-19]

          batch_infos = batch.getElementsByTagName('batch_info')
          for batch_info in batch_infos:
            batch_desc = str(batch_info.getElementsByTagName('desc')[0].childNodes[0].nodeValue)
            batch_name = str(batch_info.getElementsByTagName('name')[0].childNodes[0].nodeValue)
            batch_owner = str(batch_info.getElementsByTagName('owner')[0].childNodes[0].nodeValue)
            project_name = str(batch_info.getElementsByTagName('proj')[0].childNodes[0].nodeValue)
            tech_info = str(batch_info.getElementsByTagName('tech_info')[0].childNodes[0].nodeValue)
            umid_end = str(batch_info.getElementsByTagName('umid_end')[0].childNodes[0].nodeValue)
            umid_start = str(batch_info.getElementsByTagName('umid_start')[0].childNodes[0].nodeValue)

          # Find the project id
          query = """select id from PROJECT_TABLE where name ='%s'""" %(project_name)
          cursor.execute(query)
          projectid = cursor.fetchone()[0]

          print "batch_desc: "+batch_desc
          #print "batch_name: "+batch_name
          print "batch_owner: "+batch_owner
          print "project_name: "+project_name
          print "tech_info: "+tech_info
          #print "umid_start: "+umid_start
          #print "umid_end: "+umid_end
          #print "projectid: "+str(projectid)

          # Parse the config xmlfile
          xmldoc2 = minidom.parse(project_dir+MODEL_CONFIG_FOLDER)
          model_configs = xmldoc2.getElementsByTagName('model_config')
          for model_config in model_configs:
            horiz_resolution = str(model_config.getElementsByTagName('horiz_resolution')[0].childNodes[0].nodeValue)
            vert_resolution = str(model_config.getElementsByTagName('vert_resolution')[0].childNodes[0].nodeValue)
            grid_type = str(model_config.getElementsByTagName('grid_type')[0].childNodes[0].nodeValue)
            timestep = str(model_config.getElementsByTagName('timestep')[0].childNodes[0].nodeValue)
            timestep_units = str(model_config.getElementsByTagName('timestep_units')[0].childNodes[0].nodeValue)
            namelist_template = str(model_config.getElementsByTagName('namelist_template_global')[0].childNodes[0].nodeValue)

            #print "horiz_resolution: "+horiz_resolution
            #print "vert_resolution: "+vert_resolution
            #print "grid_type: "+grid_type
            #print "timestep: "+timestep
            #print "timestep_units: "+timestep_units
            print "namelist_template: "+namelist_template

          first_wuid = wuid+1
          first_start_year = 9999
          last_start_year = 0

          # Iterate over the workunits in the xmlfile
          workunits = batch.getElementsByTagName('workunit')
          for workunit in workunits:
            number_of_workunits = number_of_workunits+1
            analysis_member_number = str(workunit.getElementsByTagName('analysis_member_number')[0].childNodes[0].nodeValue)
            ensemble_member_number = str(workunit.getElementsByTagName('ensemble_member_number')[0].childNodes[0].nodeValue)
            exptid = str(workunit.getElementsByTagName('exptid')[0].childNodes[0].nodeValue)
            fclen = str(workunit.getElementsByTagName('fclen')[0].childNodes[0].nodeValue)
            fclen_units = str(workunit.getElementsByTagName('fclen_units')[0].childNodes[0].nodeValue)
            start_day = int(workunit.getElementsByTagName('start_day')[0].childNodes[0].nodeValue)
            start_hour = int(workunit.getElementsByTagName('start_hour')[0].childNodes[0].nodeValue)
            start_month = int(workunit.getElementsByTagName('start_month')[0].childNodes[0].nodeValue)
            start_year = int(workunit.getElementsByTagName('start_year')[0].childNodes[0].nodeValue)
            unique_member_id = str(workunit.getElementsByTagName('unique_member_id')[0].childNodes[0].nodeValue)

            # Set the first_start_year
            if start_year < first_start_year:
              first_start_year = start_year

            # Set the last_start_year
            if start_year > last_start_year:
              last_start_year = start_year

            # Set the workunit id and file names
            wuid = wuid + 1
            last_wuid = wuid
            ic_ancil_zip = "ic_ancil_"+str(wuid)+".zip"
            ifsdata_zip = "ifsdata_"+str(wuid)+".zip"
            climate_data_zip = "clim_data_"+str(wuid)+".zip"

            # Check the grid_type is an acceptable value, one of: 
            # l_2 is linear grid, _2 is quadratic grid, _full is full grid, _3 is cubic grid, _4 is octahedral cubic grid
            if grid_type not in ('l_2','_2','_full','_3','_4'):
               raise ValueError('Invalid grid_type')

            print "--------------------------------------"
            print "wuid:" +str(wuid)
            print "batchid: "+str(batchid)
            #print "analysis_member_number: "+analysis_member_number
            #print "ensemble_member_number: "+ensemble_member_number
            #print "exptid: "+exptid
            #print "fclen: "+fclen
            #print "fclen_units: "+fclen_units
            #print "start_day: "+str(start_day)
            #print "start_hour: "+str(start_hour)
            #print "start_month: "+str(start_month)
            #print "start_year: "+str(start_year)
            #print "unique_member_id: "+unique_member_id

            # Set the start_date field
            if str(start_year) is None or start_year <= 0:
               start_date = '0000'
            else:
               start_date = str(start_year)

            if str(start_month) is None or start_month <= 0:
               start_date = start_date + '00'
            elif start_month > 0 and start_month < 10:
               start_date = start_date + '0' + str(start_month)
            elif start_month < 13 and start_month > 9:
               start_date = start_date + str(start_month)

            if str(start_day) is None or start_day <= 0:
               start_date = start_date + '00'
            elif start_day > 0 and start_day < 10:
               start_date = start_date + '0' + str(start_day)
            elif start_day < 32 and start_day > 9:
               start_date = start_date + str(start_day)

            if str(start_hour) is None or start_hour <= 0:
               start_date = start_date + '00'
            elif start_hour > 0 and start_hour < 10:
               start_date = start_date + '0' + str(start_hour)
            elif start_hour < 25 and start_hour > 9:
               start_date = start_date + str(start_hour)

            # Set the name of the workunit
            workunit_name = 'openifs_'+str(unique_member_id)+'_'+str(start_date)+'_'+str(fclen)+'_'+str(batchid)+'_'+str(wuid)

            # Construct ancil_file_location
            ancil_file_location = project_dir+"oifs_ancil_files/"
            ic_ancil_location = project_dir+"oifs_ancil_files/ic_ancil/"+str(exptid)+"/"+str(start_date)+"/"+str(analysis_member_number)+"/"

            ic_ancils = workunit.getElementsByTagName('ic_ancil')
            for ic_ancil in ic_ancils:
                ic_ancil_zip_in = str(ic_ancil.getElementsByTagName('ic_ancil_zip')[0].childNodes[0].nodeValue)

            # Test whether the ic_ancil_zip is present
            try:
              os.path.exists(ic_ancil_location+str(ic_ancil_zip_in))
            except OSError:
              print "The following file is not present in the oifs_ancil_files: "+ic_ancil_zip_in

            # Change to the download dir and create link to file
            download_dir = project_dir + "/download/"
            os.chdir(download_dir)
            args = ['ln','-s',ic_ancil_location+str(ic_ancil_zip_in),ic_ancil_zip]
            p = subprocess.Popen(args)
            p.wait()


            ifsdatas = workunit.getElementsByTagName('ifsdata')
            for ifsdata in ifsdatas:
              CFC_zip = str(ifsdata.getElementsByTagName('CFC_zip')[0].childNodes[0].nodeValue)
              radiation_zip = str(ifsdata.getElementsByTagName('radiation_zip')[0].childNodes[0].nodeValue)
              SO4_zip = str(ifsdata.getElementsByTagName('SO4_zip')[0].childNodes[0].nodeValue)

            # Make a temporary directory for reorganising the files required by the workunit
            os.mkdir(project_dir+"temp")

            # Copy each of the ifsdata zip files to the temp directory
            copyfile(ancil_file_location+"ifsdata/CFC_files/"+CFC_zip,project_dir+"temp/"+CFC_zip)
            copyfile(ancil_file_location+"ifsdata/radiation_files/"+radiation_zip,project_dir+"temp/"+radiation_zip)
            copyfile(ancil_file_location+"ifsdata/SO4_files/"+SO4_zip,project_dir+"temp/"+SO4_zip)

            # Unzip each of the ifsdata files in the temp directory
            zip_file = zipfile.ZipFile(project_dir+"temp/"+CFC_zip,'r')
            zip_file.extractall(project_dir+"temp/")
            zip_file.close()
            zip_file = zipfile.ZipFile(project_dir+"temp/"+radiation_zip,'r')
            zip_file.extractall(project_dir+"temp/")
            zip_file.close()
            zip_file = zipfile.ZipFile(project_dir+"temp/"+SO4_zip,'r')
            zip_file.extractall(project_dir+"temp/")
            zip_file.close()

            # Zip together the ifsdata files
            os.chdir(project_dir+"temp")
            zip_file = zipfile.ZipFile(download_dir+'ifsdata_'+str(wuid)+'.zip','w')
            zip_file.write("C11CLIM")
            zip_file.write("C12CLIM")
            zip_file.write("C22CLIM")
            zip_file.write("CCL4CLIM")
            zip_file.write("CH4CLIM")
            zip_file.write("CO2CLIM")
            zip_file.write("ECOZC")
            zip_file.write("GCH4CLIM")
            zip_file.write("GCO2CLIM")
            zip_file.write("GOZOCLIM")
            zip_file.write("MCICA")
            zip_file.write("N2OCLIM")
            zip_file.write("NO2CLIM")
            zip_file.write("OZOCLIM")
            zip_file.write("RADRRTM")
            zip_file.write("RADSRTM")
            zip_file.write("SO4_A1B2000")
            zip_file.write("SO4_A1B2010")
            zip_file.write("SO4_A1B2020")
            zip_file.write("SO4_A1B2030")
            zip_file.write("SO4_A1B2040")
            zip_file.write("SO4_A1B2050")
            zip_file.write("SO4_A1B2060")
            zip_file.write("SO4_A1B2070")
            zip_file.write("SO4_A1B2080")
            zip_file.write("SO4_A1B2090")
            zip_file.write("SO4_A1B2100")
            zip_file.write("SO4_OBS1920")
            zip_file.write("SO4_OBS1930")
            zip_file.write("SO4_OBS1940")
            zip_file.write("SO4_OBS1950")
            zip_file.write("SO4_OBS1960")
            zip_file.write("SO4_OBS1970")
            zip_file.write("SO4_OBS1980")
            zip_file.write("SO4_OBS1990")
            zip_file.close()

            # Change the working path and delete the temp folder
            os.chdir(project_dir)
            args = ['rm','-rf','temp']
            p = subprocess.Popen(args)
            p.wait()

            climate_datas = workunit.getElementsByTagName('climate_data')
            for climate_data in climate_datas:
                climate_data_zip_in = str(climate_data.getElementsByTagName('climate_data_zip')[0].childNodes[0].nodeValue)

            # Test whether the climate_data_zip is present
            try:
              os.path.exists(ancil_file_location+"climate_data/"+str(climate_data_zip_in))
            except OSError:
              print "The following file is not present in the oifs_ancil_files: "+str(climate_data_zip_in)

            # Change to the download dir and create link to file
            os.chdir(download_dir)
            args = ['ln','-s',ancil_file_location+"climate_data/"+str(climate_data_zip_in),climate_data_zip]
            p = subprocess.Popen(args)
            p.wait()


            # Set the fpops_est and fpops_bound for the workunit
            fpops_est = str(flops_factor * int(fclen))
            fpops_bound = str(flops_factor * int(fclen) * 10)
            #print "fpops_est: "+fpops_est
            #print "fpops_bound: "+fpops_bound

            # Calculate the number of timesteps from the number of days of the simulation
            if fclen_units == 'days':
              num_timesteps = (int(fclen) * 86400)/int(timestep)
              #print "timestep: "+str(timestep)
              #print "num_timesteps: "+str(num_timesteps)

              # Throw an error if not cleanly divisible
              if not(isinstance(num_timesteps,int)):
                raise ValueError('Length of simulation (in days) does not divide equally by timestep')

            # Read in the namelist template file
            with open(project_dir+'oifs_workgen/namelist_template_files/'+namelist_template, 'r') as file :
              template_file = file.read()

            # Replace the values
            template_file = template_file.replace('_EXPTID',exptid)
            template_file = template_file.replace('_UNIQUE_MEMBER_ID',unique_member_id)
            template_file = template_file.replace('_IC_ANCIL_FILE',"ic_ancil_"+str(wuid))
            template_file = template_file.replace('_IFSDATA_FILE',"ifsdata_"+str(wuid))
            template_file = template_file.replace('_CLIMATE_DATA_FILE',"clim_data_"+str(wuid))
            template_file = template_file.replace('_HORIZ_RESOLUTION',horiz_resolution)
            template_file = template_file.replace('_GRID_TYPE',grid_type)
            template_file = template_file.replace('_NUM_TIMESTEPS',str(num_timesteps))
            template_file = template_file.replace('_TIMESTEP',timestep)

            # Write out the workunit file
            with open('fort.4', 'w') as workunit_file:
              workunit_file.write(template_file)
            workunit_file.close()

            # Zip together the fort.4 and wam_namelist files
            zip_file = zipfile.ZipFile(download_dir+workunit_name+'.zip','w')
            zip_file.write('fort.4')
            zip_file.write(project_dir+'oifs_workgen/namelist_template_files/wam_namelist')
            zip_file.close()

            # Remove the fort.4 file
            args = ['rm','-f','fort.4']
            p = subprocess.Popen(args)
            p.wait()	   

            # Test whether the workunit_name_zip is present
            try:
              os.path.exists(download_dir+workunit_name+'.zip')
            except OSError:
              print "The following file is not present in the download files: "+workunit_name+'.zip'

            # Test whether the ifsdata_zip is present
            try:
              os.path.exists(download_dir+ifsdata_zip)
            except OSError:
              print "The following file is not present in the download files: "+ifsdata_zip

            # Construct the input template
            input_string="<input_template>\n" +\
              "<file_info>\n" +\
              "   <number>0</number>\n" +\
              "</file_info>\n" +\
              "<file_info>\n" +\
              "   <number>1</number>\n" +\
              "</file_info>\n" +\
              "<file_info>\n" +\
              "   <number>2</number>\n" +\
              "</file_info>\n" +\
              "<file_info>\n" +\
              "   <number>3</number>\n" +\
              "</file_info>\n" +\
              "<workunit>\n" +\
              "   <file_ref>\n" +\
              "     <file_number>0</file_number>\n" +\
              "     <open_name>"+workunit_name+".zip</open_name>\n" +\
              "   </file_ref>\n" +\
              "   <file_ref>\n" +\
              "     <file_number>1</file_number>\n" +\
              "     <open_name>"+str(ic_ancil_zip)+"</open_name>\n" +\
              "   </file_ref>\n" +\
              "   <file_ref>\n" +\
              "     <file_number>2</file_number>\n" +\
              "     <open_name>"+str(ifsdata_zip)+"</open_name>\n" +\
              "   </file_ref>\n" +\
              "   <file_ref>\n" +\
              "     <file_number>3</file_number>\n" +\
              "     <open_name>"+str(climate_data_zip)+"</open_name>\n" +\
              "   </file_ref>\n" +\
              "   <command_line> "+str(start_date)+" "+str(exptid)+" "+str(unique_member_id)+" "+str(batchid)+" "+str(wuid)+" "+str(fclen)+"</command_line>\n" +\
              "   <rsc_fpops_est>"+fpops_est+"</rsc_fpops_est>\n" +\
              "   <rsc_fpops_bound>"+fpops_est+"0</rsc_fpops_bound>\n" +\
              "   <rsc_memory_bound>2000000000</rsc_memory_bound>\n" +\
              "   <rsc_disk_bound>9000000000</rsc_disk_bound>\n" +\
              "   <delay_bound>121.000</delay_bound>\n" +\
              "   <min_quorum>1</min_quorum>\n" +\
              "   <target_nresults>1</target_nresults>\n" +\
              "   <max_error_results>2</max_error_results>\n" +\
              "   <max_total_results>2</max_total_results>\n" +\
              "   <max_success_results>1</max_success_results>\n" +\
              "</workunit>\n"+\
              "</input_template>"

            OUTPUT=open(project_dir+"templates/"+str(options.app_name)+"_in_"+str(wuid),"w")
            # Print out the input_template
            print >> OUTPUT, input_string
            OUTPUT.close()

            # Change back to the project directory
            os.chdir(project_dir)

            # Run the create_work script to create the workunit
            args = ["./bin/create_work","-appname",str(options.app_name),"-wu_name",str(workunit_name),"-wu_template",\
                    "templates/"+str(options.app_name)+"_in_"+str(wuid),"-result_template",result_template,workunit_name+".zip",\
                     str(ic_ancil_zip),str(ifsdata_zip),str(climate_data_zip)]
            #print args
            time.sleep(2)
            p = subprocess.Popen(args)
            p.wait()

            # Enter the details of the submitted workunit into the workunit_table
            query = """insert into WORKUNIT_TABLE(wuid,batch_table,umid,name,start_year,appid) values(%i,%i,'%s','%s',%i,%i)""" \
                                               %(wuid,batchid,unique_member_id,workunit_name,start_year,appid)
            cursor.execute(query)
            db.commit()

        # Check if class is not openifs
        if not non_openifs_class:
          # Substitute the values of the workunit_range and batchid into the submission XML and write out into the sent folder
          with open(input_directory+'/'+input_xmlfile) as xmlfile:
            # print "input_directory+input_xmlfile: "+input_directory+'/'+input_xmlfile
            # print "xmlfile: "+str(xmlfile)
            xmlfile_tree = ET.parse(xmlfile)
            xmlfile_root = xmlfile_tree.getroot()
            for elem in xmlfile_root.getiterator():
              try:
                elem.text = elem.text.replace('workunit_range',str(first_wuid)+','+str(last_wuid))
                elem.text = elem.text.replace('batchid',str(batchid))
              except AttributeError:
                pass
          xmlfile_tree.write(project_dir+"oifs_workgen/sent_xmls/sent-"+input_xmlfile)

          # Remove the processed input xml file from the incoming folder
          if os.path.exists(project_dir+"oifs_workgen/incoming_xmls/"+str(input_xmlfile)):
            os.remove(project_dir+"oifs_workgen/incoming_xmls/"+str(input_xmlfile))


          # Enter the details of the new batch into the batch_table
          query = """insert into BATCH_TABLE(id,name,description,first_start_year,appid,server_cgi,owner,ul_files,tech_info,\
                     umid_start,umid_end,projectid,last_start_year,number_of_workunits,max_results_per_workunit,regionid) \
                     values(%i,'%s','%s',%i,%i,'%s','%s',%i,'%s','%s','%s',%i,%i,%i,%i,%i);""" \
                     %(batchid,batch_name,batch_desc,first_start_year,appid,server_cgi,batch_owner,number_of_uploads,tech_info,\
                       umid_start,umid_end,projectid,last_start_year,number_of_workunits,max_results_per_workunit,regionid)
          #print query
          cursor.execute(query)
          db.commit()

    # Change back to the project directory
    os.chdir(project_dir)

    # Close the connection to the secondary database
    cursor.close()
    db.close()

    # Now that the submission has completed, remove lockfile
    if os.path.exists(lockfile):
      os.remove(lockfile)

    print ""
    print "--------------------------------------"
    print "Finishing submission: "+str(datetime.datetime.now())
    print "--------------------------------------"
