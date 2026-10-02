# Serveur de qualification OptiLink dans une machine virtuelle, en une commande : vagrant up
# Prérequis sur le PC : Vagrant et VirtualBox (par défaut), ou VMware Workstation avec
# Vagrant VMware Utility et « vagrant plugin install vagrant-vmware-desktop »
# (alors : vagrant up --provider vmware_desktop). Voir README, section Qualification.
#
# Réglages possibles avant vagrant up (PowerShell) :
#   $env:OPTILINK_IP = "192.168.1.50"     adresse fixe sur le réseau du magasin
#   $env:OPTILINK_MEMOIRE = "8192"        mémoire en Mo (4096 par défaut)
#   $env:OPTILINK_CPUS = "4"              cœurs (2 par défaut)
#   $env:OPTILINK_CARTE = "Intel(R) Ethernet Connection I219-V"
#                                         carte réseau du PC pour le pont (VirtualBox) ; sinon
#                                         Vagrant la demande. Liste : VBoxManage list bridgedifs

IP = ENV.fetch("OPTILINK_IP", "192.168.1.50")

Vagrant.configure("2") do |config|
  config.vm.box = "bento/ubuntu-24.04"
  config.vm.hostname = "optilink-qualif"

  # Carte « Bridged » : le serveur a sa propre adresse sur le réseau du magasin et les postes
  # de caisse le joignent. La carte NAT de Vagrant sert seulement à sortir vers Internet.
  config.vm.network "public_network", ip: IP, bridge: ENV["OPTILINK_CARTE"]

  config.vm.provider "virtualbox" do |vbox|
    vbox.name = "optilink-qualif"
    vbox.memory = ENV.fetch("OPTILINK_MEMOIRE", "4096").to_i
    vbox.cpus = ENV.fetch("OPTILINK_CPUS", "2").to_i
  end

  config.vm.provider "vmware_desktop" do |vmware|
    vmware.gui = false
    vmware.vmx["displayName"] = "optilink-qualif"
    vmware.vmx["memsize"] = ENV.fetch("OPTILINK_MEMOIRE", "4096")
    vmware.vmx["numvcpus"] = ENV.fetch("OPTILINK_CPUS", "2")
  end

  # Le code est copié de /vagrant vers /opt/optilink, puis Docker et OptiLink sont installés.
  config.vm.provision "shell", path: "deploy/qualification/provision.sh", env: { "OPTILINK_IP" => IP }
end
