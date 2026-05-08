terraform {
  required_version = ">= 1.6.0"
}

module "todo_platform" {
  source = "../../modules"

  environment = "dev"
}

