FROM apache/spark:3.5.1

   USER root
   RUN apt-get update && apt-get install -y openjdk-17-jdk curl wget && rm -rf /var/lib/apt/lists/*
   ENV SPARK_HOME=/opt/spark
   ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

   # Копируем конфиги и JAR-ы
   COPY jars/*.jar /opt/spark/jars/
   COPY conf/spark-defaults.conf /opt/spark/conf/spark-defaults.conf
   WORKDIR /opt/spark