#!/bin/bash

# Install latest PlantUML
echo "Downloading latest PlantUML..."
wget https://github.com/plantuml/plantuml/releases/latest/download/plantuml.jar -O plantuml.jar

echo "Installing PlantUML..."
sudo mkdir -p /opt/plantuml
sudo mv plantuml.jar /opt/plantuml/plantuml.jar
echo 'java -jar /opt/plantuml/plantuml.jar "$@"' | sudo tee /usr/local/bin/plantuml
sudo chmod +x /usr/local/bin/plantuml

echo "PlantUML installation completed!"